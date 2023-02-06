"""Module for handling submit requests"""

import logging
import re
from dataclasses import dataclass
from enum import Enum, unique
from typing import List, Literal, Optional, Union
from .util import run_cmd


@unique
class RequestState(Enum):
    """The state of a submitrequest in the Open Build Service."""

    ACCEPTED = "accepted"
    REVIEW = "review"
    DECLINED = "declined"
    NEW = "new"
    REVOKED = "revoked"
    SUPERSEDED = "superseded"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class SubmitRequest:
    """A submission request of a package from a source project to a destination
    project in the Open Build Service."""

    #: unique identifier of this SubmitRequest
    id: int

    #: the text description set by the submission author
    description: str

    #: the package's source project
    source_project: str

    #: the source package name
    source_package: str

    #: the revision of the source package which was submitted
    source_revision: str

    #: this submission's destination project
    destination_project: str

    #: state of this request
    state: RequestState

    @staticmethod
    def from_osc_output(stdout: str) -> "SubmitRequest":
        """Parse the output of :command:`osc request list $proj` and convert it
        into a :py:class:`SubmitRequest` object.


        Args:
            stdout: standard output from :command:`osc request list $proj`
                containing only a **single** request

        Returns:
            A :py:class:`SubmitRequest` object created from the parsed standard
            output of :command:`osc`.

        """

        lines = stdout.strip().splitlines()
        tmp = lines[0].split()
        id = int(tmp[0])
        # osc sometimes prints partially approved reviews as follows:
        # state: review(approved)
        # => if that happens, just take the first part, as the SR is still in
        # review
        state_str = tmp[1].split(":")[1]
        if match_res := re.match(r"^(?P<state>\S+)\(\S+\)$", state_str):
            state_str = match_res.group("state")
        state = RequestState(state_str)

        # osc changed its output around 1.0.0~b4 so that the submit: line is now
        # in the 3rd line and the second is "Creade by: $user"
        submit_idx = 1
        if lines[1].split()[0] == "Created":
            submit_idx = 2
        submit, full_src, arrow, dest = lines[submit_idx].split()
        assert submit == "submit:" and arrow == "->", "malformed request output"

        # grabbing the description is a bit ugly, because it can span multiple lines:
        #        Descr: ð: sync package with openSUSE.org:devel:BCI:SLE-15-SP4 from
        #               OBS
        #
        # we proceed as follows:
        # - calculate the number of leading spaces from the second line via a regex
        # - iterate over all lines until the first non-whitespace string is Descr:
        # - save everything after 'Descr:' into description and set a flag that
        #   the description field has been seen
        # - if the description field was seen and the line has indent +
        #   len("Descr:") leading whitespaces, then it is a continuation of the
        #   description and we append it. if not, then we quit.
        match = re.match(r"(?P<indent>^\s+)", lines[submit_idx])
        assert match
        indent = match.group("indent")

        description: Optional[str] = None
        description_started = False
        for line in lines[submit_idx + 1 :]:
            tmp = line.split()
            if description_started:
                indent_length = len(indent) + len("Descr: ")
                is_continued_descr = line[:indent_length] == " " * indent_length
                if is_continued_descr:
                    assert description
                    description += " " + line.lstrip()
                    continue
                else:
                    description_started = False
                    break

            if tmp[0] != "Descr:":
                continue

            description_started = True
            description = " ".join(tmp[1:])

        if not description:
            raise ValueError(f"Submitrequest contains no description: {stdout}")

        src, rev = full_src.split("@")
        prj, pkg = src.split("/")
        return SubmitRequest(
            id=int(id),
            state=state,
            destination_project=dest,
            source_project=prj,
            source_package=pkg,
            source_revision=rev,
            description=description,
        )


def _submit_requests_from_osc(stdout: str) -> List[SubmitRequest]:
    if "No results for package" in stdout:
        return []

    res: List[SubmitRequest] = []
    for chunk in stdout.split(
        """

"""
    ):
        res.append(SubmitRequest.from_osc_output(chunk))

    return res


async def fetch_submitrequests(
    project: str,
    package: str,
    osc_cli: str = "osc",
    submit_request_states: Optional[Union[List[RequestState], Literal["all"]]] = None,
    logger: Optional[logging.Logger] = None,
) -> List[SubmitRequest]:
    """Retrieves the list of submitrequests for the project & package.

    Args:
        project: the source project
        package: the source package
        osc_cli: the command that will be used to invoke
            :command:`osc`. Defaults to plain :command:`osc`.
        submit_request_states: Optional list of request states that should be
            searched for. If no values are provided, then this defaults to
            :py:attr:`RequestState.NEW`, :py:attr:`RequestState.REVIEW`,
            :py:attr:`RequestState.DECLINED`
        logger: an optional logger for debug logging of the calls to
            :command:`osc`

    Returns:
        A list of open submit requests with the provided states.
    """
    states: str
    if submit_request_states is None or isinstance(submit_request_states, list):
        states = ",".join(
            str(state)
            for state in (
                submit_request_states
                or [RequestState.NEW, RequestState.REVIEW, RequestState.DECLINED]
            )
        )
    else:
        states = submit_request_states

    return _submit_requests_from_osc(
        (
            await run_cmd(
                f"{osc_cli} request list -s {states} -t submit {project}/{package}",
                logger=logger,
            )
        ).stdout.strip()
    )
