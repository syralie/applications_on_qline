# QToken QLine

Python implementation of the QT1 quantum token exchange protocol.

## Installation

```bash
pip install -r requirements.txt
pip install -e .
```

## Tests

### Without hardware simulation

```bash
./scripts/test_protocol_no_hw.sh 2
```

### With hardware simulation (requires kiwi_hw_control)

```bash
./scripts/test_protocol_w_hw.sh 2
```

## Structure

- `src/alice/` : Alice implementation
- `src/bob/` : Bob implementation
- `src/agents/` : Distributed agents
- `src/utils/` : Utilities and readers
- `scripts/` : Test scripts

## Usage

### Manual mode (default values)

```bash
# Terminal 1: Bob
python run_bob.py --M 2

# Terminal 2: Bob agents (4 for M=2)
python run_bob_agent.py --M 2 --pid 00
python run_bob_agent.py --M 2 --pid 01
python run_bob_agent.py --M 2 --pid 10
python run_bob_agent.py --M 2 --pid 11

# Terminal 3: Alice
python run_alice.py --M 2

# Terminal 4: Alice agents (4 for M=2)
python run_alice_agent.py --M 2 --pid 00 --al_port 65000
python run_alice_agent.py --M 2 --pid 01 --al_port 65000
python run_alice_agent.py --M 2 --pid 10 --al_port 65000
python run_alice_agent.py --M 2 --pid 11 --al_port 65000
```

### Hardware simulation mode

```bash
# Launch hardware simulation (requires kiwi_hw_control)
./scripts/launch_simulation.sh

# Launch protocol with simulation
./scripts/test_protocol_w_hw.sh 2 10 0.11
```

## Parameters

- `M` : Number of bits to identify agents (2^M agents)
- `--sim` : Use hardware simulation
- `--bit_size` : Token size in bits
- `--gamma-err` : Error rate threshold for verification
- `--gamma-det` : Detection rate threshold

## Dependencies

This project uses only the Python standard library (asyncio, json, logging, argparse, etc.). No third-party packages are required at runtime.

Development tools (optional):
- [pytest](https://docs.pytest.org/) (MIT License)
- [black](https://black.readthedocs.io/) (MIT License)
- [pylint](https://pylint.readthedocs.io/) (GPL-2.0 License)
- [flake8](https://flake8.pycqa.org/) (MIT License)
- [mypy](https://mypy-lang.org/) (MIT License)


## License

This project is licensed under the [GPL-2.0](LICENSE).


## Reference

Kent et al. 2022, "Practical quantum tokens without quantum memories"
