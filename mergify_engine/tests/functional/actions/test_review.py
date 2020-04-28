# -*- encoding: utf-8 -*-
#
# Copyright © 2020 Mergify SAS
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
import yaml

from mergify_engine import context
from mergify_engine.tests.functional import base


class TestReviewAction(base.FunctionalTestBase):
    def test_review(self):
        rules = {
            "pull_request_rules": [
                {
                    "name": "approve",
                    "conditions": [f"base={self.master_branch_name}"],
                    "actions": {"review": {"type": "APPROVE"}},
                },
                {
                    "name": "requested",
                    "conditions": [
                        f"base={self.master_branch_name}",
                        "#approved-reviews-by>=1",
                    ],
                    "actions": {
                        "review": {"message": "WTF?", "type": "REQUEST_CHANGES"}
                    },
                },
            ]
        }

        self.setup_repo(yaml.dump(rules))

        p, _ = self.create_pr()

        self.wait_for("pull_request_review", {}),

        p.update()
        comments = list(p.get_reviews())
        self.assertEqual(2, len(comments))
        self.assertEqual("APPROVED", comments[-2].state)
        self.assertEqual("CHANGES_REQUESTED", comments[-1].state)
        self.assertEqual("WTF?", comments[-1].body)

    def test_review_template(self):
        rules = {
            "pull_request_rules": [
                {
                    "name": "approve",
                    "conditions": [f"base={self.master_branch_name}"],
                    "actions": {"review": {"type": "APPROVE"}},
                },
                {
                    "name": "requested",
                    "conditions": [
                        f"base={self.master_branch_name}",
                        "#approved-reviews-by>=1",
                    ],
                    "actions": {
                        "review": {
                            "message": "WTF {{author}}?",
                            "type": "REQUEST_CHANGES",
                        }
                    },
                },
            ]
        }

        self.setup_repo(yaml.dump(rules))

        p, _ = self.create_pr()

        self.wait_for("pull_request_review", {}),

        p.update()
        comments = list(p.get_reviews())
        self.assertEqual(2, len(comments))
        self.assertEqual("APPROVED", comments[-2].state)
        self.assertEqual("CHANGES_REQUESTED", comments[-1].state)
        self.assertEqual(f"WTF {self.u_fork.login}?", comments[-1].body)

    def _test_review_template_error(self, msg):
        rules = {
            "pull_request_rules": [
                {
                    "name": "approve",
                    "conditions": [f"base={self.master_branch_name}"],
                    "actions": {"review": {"type": "APPROVE"}},
                },
                {
                    "name": "review",
                    "conditions": [
                        f"base={self.master_branch_name}",
                        "#approved-reviews-by>=1",
                    ],
                    "actions": {"review": {"message": msg, "type": "REQUEST_CHANGES"}},
                },
            ]
        }

        self.setup_repo(yaml.dump(rules))

        p, _ = self.create_pr()

        self.wait_for("pull_request_review", {}),

        p.update()

        ctxt = context.Context(self.cli_integration, p.raw_data, {})
        checks = list(
            c
            for c in ctxt.pull_engine_check_runs
            if c["name"] == "Rule: review (review)"
        )

        assert len(checks) == 1
        return checks[0]

    def test_review_template_syntax_error(self):
        check = self._test_review_template_error(msg="Thank you {{",)
        assert "Invalid review message" == check["output"]["title"]
        assert "failure" == check["conclusion"]
        assert (
            "There is an error in your message: unexpected 'end of template' at line 1"
            == check["output"]["summary"]
        )

    def test_review_template_attribute_error(self):
        check = self._test_review_template_error(msg="Thank you {{hello}}",)
        assert "failure" == check["conclusion"]
        assert "Invalid review message" == check["output"]["title"]
        assert (
            "There is an error in your message, the following variable is unknown: hello"
            == check["output"]["summary"]
        )