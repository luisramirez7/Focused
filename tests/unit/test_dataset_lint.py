from inbox_agent.evals.lint_dataset import lint


def test_golden_set_has_no_lint_findings():
    findings = lint()
    assert not findings, "\n".join(f"{f.id} {f.code}: {f.message}" for f in findings)
