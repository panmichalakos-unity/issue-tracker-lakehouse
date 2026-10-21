"""Run the same end-to-end verification locally and in GitHub Actions."""

from pathlib import Path
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DBT = ('from dbt.cli.main import dbtRunner; import sys; '
       'result=dbtRunner().invoke(sys.argv[1:]); '
       'sys.exit(0 if result.success else 1)')


def run(arguments, cwd=ROOT):
    print('+', ' '.join(arguments), flush=True)
    subprocess.run([sys.executable, *arguments], cwd=cwd, check=True)


def main():
    os.environ['DBT_SEND_ANONYMOUS_USAGE_STATS'] = 'false'
    os.environ['DO_NOT_TRACK'] = '1'
    run(['-m', 'pytest', '-q'])
    run(['-m', 'ingest'])
    run(['-c', DBT, 'build', '--profiles-dir', '.', '--no-use-colors'], ROOT / 'dbt')
    run(['-m', 'ingest'])
    run(['-m', 'ingest', '--incremental'])
    run(['-c', DBT, 'build', '--profiles-dir', '.', '--no-use-colors'], ROOT / 'dbt')
    run(['-c', 'import duckdb; c=duckdb.connect("data/warehouse.duckdb",read_only=True); '
         'n=c.sql("select count(*) from bronze.issues").fetchone()[0]; '
         'assert n==34, n; print("Verified:",n,"issues after repeated and incremental runs"); c.close()'])


if __name__ == '__main__':
    main()
