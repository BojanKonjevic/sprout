import pytest

from __PKG_NAME__.main import main


def test_main(capsys: pytest.CaptureFixture[str]) -> None:
    main()
    captured = capsys.readouterr()
    assert "Hello from __NAME__" in captured.out
