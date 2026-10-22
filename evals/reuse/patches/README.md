# Public example CLI patch

`python-slugify-8.0.4-cli-regex.patch` forwards the already parsed `--regex-pattern` argument to `slugify()`. It applies to a **copy** of python-slugify tag `v8.0.4`, commit `f85f9488520148d5f6899b5639199882b605e30a` from [un33k/python-slugify](https://github.com/un33k/python-slugify/tree/v8.0.4). The original is MIT; preserve its LICENSE and attribution. This patch is a separate exercise artifact, not a patch to word-skills or an upstream contribution.

Apply with `git apply PATH_TO_PATCH` inside a fresh copy. Compare `python -m slugify --regex-pattern "[^a-z]+" "abc123"`: the original CLI returns `abc123`, the patched CLI and direct Python function return `abc`. Default CLI output remains `abc123` in both versions. Test against the actual copied code, not an expected-output mock. Do not alter the fixed original snapshot or retrospectively relabel its manual as testing the patched version. No issue, PR or message has been sent upstream.
