# `.mnemosyneignore` reference

Place a `.mnemosyneignore` file at the repository root to exclude paths from
documentation capture, file-tree records, and embeddings. Matching content is
never stored.

## Syntax (gitignore-style subset)

```text
# comment lines and blanks are skipped
.env.*              # basename glob — matches at any depth
secrets/            # single-segment directory — matches at any depth
internal/legal/     # multi-segment directory — prefix match from the root
src/payments/**     # path glob
*.pem               # extension glob
```

## Always-on global denylist

Regardless of `.mnemosyneignore`, Mnemosyne never captures:

```text
.env  .env.*  *.pem  *.key  *.crt  *.p12  *.sqlite  *.db
secrets/  credentials/  private/  node_modules/  dist/  build/  target/
.venv/  __pycache__/
```

## Secret quarantine

Captured documents are scanned (token patterns + entropy) before persistence.
A document containing a detected secret is stored as **metadata only**
(path/type/hash), flagged `quarantined`, and excluded from embeddings and
agent responses.
