"""Allow ``python -m boatrace_cal`` to run the CLI in source checkouts."""

from boatrace_cal.cli import main


raise SystemExit(main())
