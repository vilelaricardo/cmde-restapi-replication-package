# OpenAPI specifications of the CMDE API

Two versions of the CMDE API's OpenAPI document, the before and after of the
specification findings reported in the paper (Section "Observed
Specification-Runtime Mismatches").

| File | Version | Paths | Operations | SHA-256 |
|---|---|---|---|---|
| `archived/api-docs.json` | 0.5.9 | 48 | 58 | `1a91e156081ae31ec98eb247b8076a3fa07fb6963ea3295b1dbf20ed1fd18d33` |
| `corrected/api-docs.json` | 0.6.11 | 57 | 72 | `47155f492094eda0884b4ac23468de44719774cff2c4a13aab1469d96a836eb4` |

- **`archived/`** is the specification used by the initial study and by the
  2026 campaigns. It is the same file as `results/official-run/api-docs.json`
  and as the `api-docs.json` stored with each campaign's raw data.
- **`corrected/`** was retrieved from the public documentation of the API,
  <https://api-cmde.gestaopresente.mec.gov.br/docs?api-docs.json>, after the
  development team declared the missing status codes. The public document may
  change again, so this copy, not the URL, is the reference for the paper.

Both files are public documentation of the API and are included without
changes.
