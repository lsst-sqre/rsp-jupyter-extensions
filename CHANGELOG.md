# Change log

rsp-jupyter-extensions is versioned with [semver](https://semver.org/). Dependencies are updated to the latest available version during each release. Those changes are not noted here explicitly.

Find changes for the upcoming release in the project's [changelog.d](https://github.com/lsst-sqre/rsp-jupyter-extensions/tree/main/changelog.d/).

<a id='changelog-0.27.3'></a>

## 0.27.3 (2026-08-26)

### New features

- Add ENOWRITEABLESERVERROOT to errors.

<a id='changelog-0.27.2'></a>

### New features

- Add information about NB_HOME to quota/out-of-space message, if we have it.

<a id='changelog-0.27.1'></a>

## 0.27.1 (2026-08-10)

### New features

- Simplified PDF export handling; no pandoc, only Callisto >= 0.3.0

<a id='changelog-0.27.0'></a>

## 0.27.0 (2026-07-23)

### Backwards-incompatible changes

- Pulled out jupyter-server-documents and jupyter-collaboration; added manual saving back.

### Other changes

- Removed unnecessary version pins and cleaned up stale commentary.

<a id='changelog-0.26.0'></a>

## 0.26.0 (2026-07-15)

### New features

- Add collab_dir to config and generate second filebrowser from it.

### Other changes

- Modernize build machinery.

<a id='changelog-v0.25.0'></a>

## v0.25.0 (2026-05-26)

### New features

- Read from lab-config.json if it exists.

### Other changes

- Rebuilt package.json and tsconfig.json with current JupyterLab dependencies.

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
