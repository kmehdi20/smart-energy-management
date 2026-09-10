# Contributing

Contributions are welcome! Here's how to get involved.

## Reporting Issues

Open a GitHub issue with:
- A clear title
- Steps to reproduce
- Expected vs. actual behavior
- Python version and OS

## Pull Requests

1. Fork the repo
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes with tests
4. Run the test suite: `pytest tests/ -v`
5. Ensure all 47 tests still pass
6. Commit with a clear message
7. Open a PR against `main`

## Code Style

- Python: PEP 8, type hints where practical
- Docstrings for public functions
- One responsibility per module
- No hard-coded secrets — use `.env`

## Areas Open for Contribution

- Grid export / net metering support
- Weather API integration (OpenWeatherMap)
- Reinforcement learning EMS as a third strategy
- Multi-building aggregation
- Mobile app (Flutter / React Native)
- Real ESP32 firmware with actual sensors
