# Releasing

1. Update the version in `pyproject.toml`.
2. Commit the change and push.
   ```sh
   git commit -a
   git push
   ```
3. Create a new release at [Releases].
   The [`publish.yml` action]
   automatically publishes the release to [PyPI].
4. Update the version to prerelease.
5. Commit the change and push. For example:
   ```sh
   git commit -a -m 'v1.4.3-alpha.0'
   git push
   ```

The version is automatically assigned by [setuptools-scm].

[`publish.yml` action]: https://github.com/kojiishi/east_asian_spacing/blob/main/.github/workflows/publish.yml
[PyPI]: https://pypi.org/project/east-asian-spacing/
[Releases]: https://github.com/kojiishi/east_asian_spacing/releases
[setuptools-scm]: https://pypi.org/project/setuptools-scm/
