# QToken QLine - Open Source

Implementation Python du protocole d'echange de jetons quantiques QT1.

## Installation

```bash
pip install -r requirements.txt
pip install -e .
```

## Tests

### Sans simulation hardware

```bash
./scripts/test_protocol_no_hw.sh 2
```

### Avec simulation hardware (necessite kiwi_hw_control)

```bash
./scripts/test_protocol_w_hw.sh 2
```

## Structure

- `src/alice/` : Implementation d'Alice
- `src/bob/` : Implementation de Bob
- `src/agents/` : Agents distribues
- `src/utils/` : Utilitaires et readers
- `scripts/` : Scripts de test

## Usage

### Mode manuel (valeurs par defaut)

```bash
# Terminal 1: Bob
python run_bob.py --M 2

# Terminal 2: Bob agents (4 pour M=2)
python run_bob_agent.py --M 2 --pid 00
python run_bob_agent.py --M 2 --pid 01
python run_bob_agent.py --M 2 --pid 10
python run_bob_agent.py --M 2 --pid 11

# Terminal 3: Alice
python run_alice.py --M 2

# Terminal 4: Alice agents (4 pour M=2)
python run_alice_agent.py --M 2 --pid 00 --al_port 65000
python run_alice_agent.py --M 2 --pid 01 --al_port 65000
python run_alice_agent.py --M 2 --pid 10 --al_port 65000
python run_alice_agent.py --M 2 --pid 11 --al_port 65000
```

### Mode simulation hardware

```bash
# Lancer la simulation hardware (necessite kiwi_hw_control)
./scripts/launch_simulation.sh

# Lancer le protocole avec simulation
./scripts/test_protocol_w_hw.sh 2 10 0.11
```

## Parametres

- `M` : Nombre de bits pour identifier les agents (2^M agents)
- `--sim` : Utiliser la simulation hardware
- `--bit_size` : Taille du token en bits
- `--gamma-err` : Seuil de taux d'erreur pour la verification
- `--gamma-det` : Seuil de taux de detection

## Reference

Kent et al. 2022, "Practical quantum tokens without quantum memories"
