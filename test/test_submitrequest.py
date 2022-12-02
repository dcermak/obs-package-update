from typing import List
import pytest
from obs_package_update.submitrequest import (
    RequestState,
    SubmitRequest,
    _submit_requests_from_osc,
)


@pytest.mark.parametrize(
    "stdout,submit_request",
    [
        (
            """274438  State:declined   By:oertel       When:2022-06-17T14:20:09
        submit:          openSUSE.org:devel:BCI:SLE-15-SP4/ruby-2.5-image@6 -> SUSE:SLE-15-SP4:Update:BCI
        Review by Group      is accepted:  legal-auto(licensedigger)                         
        Review by Group      is new:       autobuild-team                                    
        Review by Group      is accepted:  sle-release-managers(aherzig)                     
        Descr: sync package with openSUSE.org:devel:BCI:SLE-15-SP4 from OBS
        Comment: please add some detail to the changes entry about the other
               changes,,replacing amp/amp by ; in Dockerfile 
""",
            SubmitRequest(
                id=274438,
                state=RequestState.DECLINED,
                source_project="openSUSE.org:devel:BCI:SLE-15-SP4",
                source_package="ruby-2.5-image",
                source_revision="6",
                destination_project="SUSE:SLE-15-SP4:Update:BCI",
                description="sync package with openSUSE.org:devel:BCI:SLE-15-SP4 from OBS",
            ),
        ),
        (
            """969741  State:revoked    By:dancermak    When:2022-04-13T08:45:53
        submit:          home:dancermak:auto_update:sp4/ruby-2.5-image@2 -> devel:BCI:SLE-15-SP4
        Descr: Update to the latest generator version
        Comment: The source project 'home:dancermak:auto_update:sp4' has been
               removed 
""",
            SubmitRequest(
                id=969741,
                state=RequestState.REVOKED,
                source_project="home:dancermak:auto_update:sp4",
                source_package="ruby-2.5-image",
                source_revision="2",
                destination_project="devel:BCI:SLE-15-SP4",
                description="Update to the latest generator version",
            ),
        ),
        (
            """972062  State:accepted   By:dirkmueller  When:2022-04-22T09:00:20
        submit:          home:dancermak:auto_update:sp4/ruby-2.5-image@2 -> devel:BCI:SLE-15-SP4
        Descr: remove org.opencontainers.image.revision label
""",
            SubmitRequest(
                id=972062,
                state=RequestState.ACCEPTED,
                source_project="home:dancermak:auto_update:sp4",
                source_package="ruby-2.5-image",
                source_revision="2",
                destination_project="devel:BCI:SLE-15-SP4",
                description="remove org.opencontainers.image.revision label",
            ),
        ),
        (
            """264309  State:revoked    By:dancermak    When:2022-02-08T14:45:10
        submit:          home:dancermak:auto_update:sp4/ruby-2.5-image@2 -> SUSE:SLE-15-SP4:Update:BCI
        Review by Group      is accepted:  legal-auto(licensedigger)                         
        Review by Group      is accepted:  autobuild-team(bigironman)                        
        Review by Group      is new:       sle-release-managers                              
        Descr: Update labels according to jsc#BCI-33
        Comment: The source project 'home:dancermak:auto_update:sp4' has been
               removed 
""",
            SubmitRequest(
                id=264309,
                state=RequestState.REVOKED,
                source_project="home:dancermak:auto_update:sp4",
                source_package="ruby-2.5-image",
                source_revision="2",
                destination_project="SUSE:SLE-15-SP4:Update:BCI",
                description="Update labels according to jsc#BCI-33",
            ),
        ),
        (
            """275743  State:new        By:bigironman   When:2022-07-15T09:34:59
        submit:          openSUSE.org:devel:BCI:SLE-15-SP4/rust-1.60-image@6 -> SUSE:SLE-15-SP4:Update:BCI
        Review by Group      is accepted:  legal-auto(licensedigger)                         
        Review by Group      is accepted:  autobuild-team(bigironman)                        
        Review by Group      is accepted:  sle-release-managers(aherzig)                     
        Descr: ð: sync package with openSUSE.org:devel:BCI:SLE-15-SP4 from
               OBS
        Comment: All reviewers accepted request 
""",
            SubmitRequest(
                id=275743,
                state=RequestState.NEW,
                source_project="openSUSE.org:devel:BCI:SLE-15-SP4",
                source_package="rust-1.60-image",
                source_revision="6",
                destination_project="SUSE:SLE-15-SP4:Update:BCI",
                description="ð: sync package with openSUSE.org:devel:BCI:SLE-15-SP4 from OBS",
            ),
        ),
        (
            """285603  State:review(approved) By:dancermak    When:2022-12-01T12:46:57
        submit:          openSUSE.org:devel:BCI:SLE-15-SP5/389-ds-container@2 -> SUSE:SLE-15-SP5:Update:BCI
        Review by Group      is accepted:  legal-auto(licensedigger)                         
        Review by Group      is accepted:  autobuild-team(dmach)                             
        Review by Group      is new:       sle-release-managers                              
        Descr: 🤖: sync package with openSUSE.org:devel:BCI:SLE-15-SP5 from OBS
""",
            SubmitRequest(
                id=285603,
                state=RequestState.REVIEW,
                source_project="openSUSE.org:devel:BCI:SLE-15-SP5",
                source_package="389-ds-container",
                description="🤖: sync package with openSUSE.org:devel:BCI:SLE-15-SP5 from OBS",
                source_revision="2",
                destination_project="SUSE:SLE-15-SP5:Update:BCI",
            ),
        ),
    ],
)
def test_from_osc_stdout(stdout: str, submit_request: SubmitRequest):
    assert submit_request == SubmitRequest.from_osc_output(stdout)


@pytest.mark.parametrize(
    "stdout,requests",
    [
        ("""No results for package SUSE:SLE-15-SP4:Update:BCI/init-image""", []),
        (
            """259543  State:superseded By:dancermak    When:2021-12-13T08:01:09
        submit:          home:dancermak:branches:SUSE:SLE-15-SP4:Update:BCI/ruby-2.5-image@2 -> SUSE:SLE-15-SP4:Update:BCI
        Review by Group      is accepted:  legal-auto(licensedigger)
        Review by Group      is accepted:  maintenance-team(maintenance-robot)
        Review by Group      is accepted:  autobuild-team(oertel)
        Review by Group      is new:       sle-release-managers
        Descr: Submission of the BCI image from SP3
        Comment: superseded by 260257

260257  State:superseded By:dancermak    When:2021-12-13T09:37:13
        submit:          home:dancermak:branches:SUSE:SLE-15-SP4:Update:BCI/ruby-2.5-image@3 -> SUSE:SLE-15-SP4:Update:BCI
        Review by Group      is new:       legal-auto
        Review by Group      is accepted:  maintenance-team(maintenance-robot)
        Review by Group      is new:       autobuild-team
        Review by Group      is new:       sle-release-managers
        Descr: Submission of the BCI image from SP3
        Comment: superseded by 260266

260266  State:accepted   By:aherzig      When:2021-12-14T17:08:39
        submit:          home:dancermak:branches:SUSE:SLE-15-SP4:Update:BCI/ruby-2.5-image@4 -> SUSE:SLE-15-SP4:Update:BCI
        Review by Group      is accepted:  legal-auto(licensedigger)
        Review by Group      is accepted:  autobuild-team(oertel)
        Review by Group      is accepted:  sle-release-managers(aherzig)
        Descr: Submission of the BCI image from SP3


261877  State:accepted   By:fcrozat      When:2022-01-13T15:34:19
        submit:          home:dancermak:branches:SUSE:SLE-15-SP4:Update:BCI/ruby-2.5-image@2 -> SUSE:SLE-15-SP4:Update:BCI
        Review by Group      is accepted:  legal-auto(licensedigger)
        Review by Group      is accepted:  autobuild-team(oertel)
        Review by Group      is accepted:  sle-release-managers(fcrozat)
        Descr: Cleanup /var/log
""",
            [
                SubmitRequest(
                    id=259543,
                    state=RequestState.SUPERSEDED,
                    source_project="home:dancermak:branches:SUSE:SLE-15-SP4:Update:BCI",
                    source_package="ruby-2.5-image",
                    source_revision="2",
                    destination_project="SUSE:SLE-15-SP4:Update:BCI",
                    description="Submission of the BCI image from SP3",
                ),
                SubmitRequest(
                    id=260257,
                    state=RequestState.SUPERSEDED,
                    source_project="home:dancermak:branches:SUSE:SLE-15-SP4:Update:BCI",
                    source_package="ruby-2.5-image",
                    source_revision="3",
                    destination_project="SUSE:SLE-15-SP4:Update:BCI",
                    description="Submission of the BCI image from SP3",
                ),
                SubmitRequest(
                    id=260266,
                    state=RequestState.ACCEPTED,
                    source_project="home:dancermak:branches:SUSE:SLE-15-SP4:Update:BCI",
                    source_package="ruby-2.5-image",
                    source_revision="4",
                    destination_project="SUSE:SLE-15-SP4:Update:BCI",
                    description="Submission of the BCI image from SP3",
                ),
                SubmitRequest(
                    id=261877,
                    state=RequestState.ACCEPTED,
                    source_project="home:dancermak:branches:SUSE:SLE-15-SP4:Update:BCI",
                    source_package="ruby-2.5-image",
                    source_revision="2",
                    destination_project="SUSE:SLE-15-SP4:Update:BCI",
                    description="Cleanup /var/log",
                ),
            ],
        ),
    ],
)
def test_request_list_from_osc_output(stdout: str, requests: List[SubmitRequest]):
    assert _submit_requests_from_osc(stdout) == requests
