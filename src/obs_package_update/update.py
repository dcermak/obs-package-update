from abc import ABC, abstractmethod
from datetime import timedelta
from typing import List, Optional
import aiofiles.tempfile
import logging
from dataclasses import dataclass

from obs_package_update.util import run_cmd


@dataclass
class Package:
    """Representation of a package in the Open Build Service."""

    #: the project name to which the package belongs
    project: str

    #: the package's name
    package: str

    def __str__(self) -> str:
        return f"{self.project}/{self.package}"


@dataclass
class Updater(ABC):
    """Class for updating packages in the Open Build Service.

    The core functionality that the user must provide is the method `add_files`,
    which writes the updated packages files into a destination folder where the
    current package version has been checked out. This function must return a
    list of filenames that were written into `destination`.

    Once this function has been implemented, use py:meth:`update_package` to run
    the actual update.

    """

    #: url to the API of the Open build Service instance that you are targeting
    api_url: str = "https://api.opensuse.org"

    #: An Optional logger that will be used for logging errors and debug output
    logger: Optional[logging.Logger] = None

    #: The osc command that will be used to execute the update. It defaults to
    #: :command:`osc -A $api_url` unless a value is provided
    osc_cli: Optional[str] = None

    def __post_init__(self):
        if self.osc_cli is None:
            self.osc_cli = f"osc -A {self.api_url}"

    @abstractmethod
    async def add_files(self, destination: str) -> List[str]:
        """This function will be invoked in the update process, it should create
        the new package files and return the list of files that were added.

        """

    async def update_package(
        self,
        source_package: Package,
        commit_msg: str,
        target_project: Optional[str] = None,
        cleanup_on_error: bool = False,
        submit_package: bool = True,
        cleanup_on_no_change: bool = True,
    ):
        """Updates `source_package` by branching it (optionally into
        `target_project` instead of the default location), writing the new files
        using py:meth:`add_files`, committing them, updating the changelog with
        `commit_msg` and sending a submit request back to the original project
        (unless `submit_package` is ``False``).

        If the new files created by `add_files` result in no change of the
        package, then no commit will be done and the branched package will be
        removed (unless `cleanup_on_no_change` is `False`).

        Parameters:
        source_package: the package which shall be updated
        commit_msg: the commit message that will be used for the osc commit, for
                    the changelog entry and for the submit request
        target_project: an optional alternative project into which the package
                        shall be branched instead of using the default in your
                        home project
        cleanup_on_error: if an error occurs during the update and this flag is
                          ``True``, then the package will be removed in the Open
                          Build Service
        submit_package: Flag whether to send a submit request with the update
                        (defaults to ``True``)
        cleanup_on_no_change: Flag whether to delete the package in the Open
                              Build Service, when no change was made (defaults
                              to ``True``)
        """
        assert (
            self.osc_cli
        ), f"{self.osc_cli=} must be defined, was __post_init__ not run?"

        async with aiofiles.tempfile.TemporaryDirectory() as tmp:
            if self.logger:
                self.logger.info("Updating %s", source_package)
                self.logger.debug("Running update in %s", tmp)

            async def run(cmd: str) -> str:
                res = await run_cmd(
                    cmd,
                    cwd=tmp,
                    raise_on_error=True,
                    timeout=timedelta(minutes=1),
                    logger=self.logger,
                )
                return res.stdout

            target_pkg: Optional[str] = None
            try:
                cmd = f"{self.osc_cli} branch {source_package.project} {source_package.package}"
                if target_project:
                    cmd += f" {target_project}"

                stdout = (await run(cmd)).split("\n")
                co_cmd = stdout[2]
                target_pkg = co_cmd.split(" ")[-1]

                await run(f"{self.osc_cli} co {target_pkg} -o {tmp}")

                written_files = await self.add_files(tmp)
                for fname in written_files:
                    await run(f"{self.osc_cli} add {fname}")

                st_out = await run(f"{self.osc_cli} st")
                # nothing changed => leave
                if st_out == "":
                    if self.logger:
                        self.logger.info("Nothing changed => no update available")
                    if cleanup_on_no_change:
                        await run(
                            f"{self.osc_cli} rdelete {target_pkg} -m 'cleanup as nothing changed'"
                        )
                    return

                for cmd in ["vc", "ci"]:
                    await run(f'{self.osc_cli} {cmd} -m "{commit_msg}"')

                # wait for any services to run before doing anything else
                # target_pkg is $proj/$pkg => convert to `osc service wait $proj $pkg`
                await run(f"{self.osc_cli} service wait {target_pkg.replace('/', ' ')}")

                if submit_package:
                    await run(f'{self.osc_cli} sr --cleanup -m "{commit_msg}"')

            except Exception as exc:
                if self.logger:
                    self.logger.error(
                        "failed to update %s, got %s", source_package, exc
                    )
                if cleanup_on_error and target_pkg:
                    if self.logger:
                        self.logger.info("Will cleanup %s", target_pkg)
                    await run(
                        f"{self.osc_cli} rdelete {target_pkg} -m 'cleanup on error'"
                    )
                raise exc
