import argparse

# Lidando com argumentos
parser = argparse.ArgumentParser()

# --etl
parser.add_argument("--etl", action="store_true", help="Habilita o airbyte ao executar o código")

# --etl-only
parser.add_argument("--etl-only", action="store_true", help="Roda somente o airbyte ao executar o código")

flags = parser.parse_args()
