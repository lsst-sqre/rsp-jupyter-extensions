# Change log

rsp-jupyter-extensions is versioned with [semver](https://semver.org/). Dependencies are updated to the latest available version during each release. Those changes are not noted here explicitly.

Find changes for the upcoming release in the project's [changelog.d](https://github.com/lsst-sqre/rsp-jupyter-extensions/tree/main/changelog.d/).

<!-- scriv-insert-here -->

<a id='changelog-v0.24.1'></a>
## v0.24.1 (2026-05-21)

### Other changes

- Refactor of back end server for clarity and concision.
- Add serviceinfo endpoint analogous to statusbar to reduce work done in front end.
- Make config a singleton and share it between backend components.

- Reword Exit and Logout menu items to add (Autosaving) to soothe anxiety.

<a id='changelog-0.23.0'></a>

## 0.23.0 (2026-05-04)

### Backwards-incompatible changes

- Removed save-document features from Hub interaction menu items.

### Other changes

- New package jupyter-server-documents obviates need for manual saving.
