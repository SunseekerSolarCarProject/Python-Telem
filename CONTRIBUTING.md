# Contributing

Drew Thompson with all the code currently.

Automated tests are maintained in `dev/testing/tests`. Add a focused test when
introducing behavior and a regression test when fixing a reproducible bug. Run
the full suite before submitting changes:

```bash
python dev/testing/run_tests.py
```

See `dev/testing/README.md` for naming, isolation, GUI, and external-service
testing conventions.
