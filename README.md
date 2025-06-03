# rsp_jupyter_extensions

[![Github Actions Status](https://github.com/lsst-sqre/rsp-jupyter-extensions/workflows/CI/badge.svg)](https://github.com/lsst-sqre/rsp-jupyter-extensions/actions/workflows/ci.yaml)
Jupyter Extensions for the Rubin Science Platform

This extension is composed of a Python package named `rsp_jupyter_extensions`
for the server extension and a NPM package named `rsp-jupyter-extensions`
for the frontend extension.

## RSP-Specific instructions

This is a very Rubin (and RSP, particularly)-specific package. Rubin
Observatory's development practices don't entirely track what JupyterLab
expects you to do. Some notes for use by Rubin developers follow:

If you need to change the `rsp-jupyter-extensions` package, you will
need to know that it is a [prebuilt
extension](https://jupyterlab.readthedocs.io/en/stable/extension/extension_dev.html#prebuilt-extensions>)
created from the [JupyterLab extension copier template](https://github.com/jupyterlab/extension-template).

To this copier template we have added GitHub Actions to rebuild
containers and client libraries and push them to their respective
locations in artifact registries and PyPI.

We have also added a `Makefile` and modified `pyproject.toml` in
order to make it behave more like a standard SQuaRE repository in some
ways.

The way our extensions work is that they contain both a backend server
component (written in Python, acessible under the `/rubin` endpoint
within the lab) and a frontend UI component, written in TypeScript.

A request from the user's browser (either via an action taken by a user,
or something done on UI load at startup) will go to the backend server,
and receive a reply which will guide the UI's action.

### The "prebuilt" part

The "prebuilt" part of "prebuilt extension" means both that there is no
need to install nodejs in the Lab container and that the only thing that
needs doing to activate the extension is to `pip install` it.

The build process within `rsp-jupyter-extensions` will generate and pack
the extension's JavaScript.

### Versioning the extension

One not-at-all-obvious corollary of using the `copier` template to
generate the extension framework is that we do not use the standard
SQuaRE release process to create a new version tag.

Instead the new version must be specified in `package.json` in the
extension root directory.

### Using the Makefile

We use `make` to initialize the development environment with `make init`.

`make typing` typechecks both the TypeScript UI components and the
Python server components.
As a side effect (!!) it also builds the packed Javascript that is
included with the package.

`make lint` lints both the TypeScript and the Python components.

`make test` runs the test suite for the Python back-end server.

There are not currently effective tests for the TypeScript components,
only a basic smoke test to ensure that it loads into JupyterLab without
throwing an exception.

### Developing the server backend

The server backend behaves much like a standard SQuaRE service.
It is written in typed Python and follows the usual SQuaRE guidelines
with respect to linting and typing.
It is found in the `rsp_jupyter_extensions` directory.

#### Write the service

Write your service; it almost certainly belongs in the `handlers`
subdirectory.
The handler should probably derive from the `APIHandler`
superclass; look at another handler for the pattern.
The `APIHandler`
will return JSON to the caller, which is trivially parsed by the UI
`APIRequest()` function.

If you end up requiring models of any real complexity for the extension,
put them in the `models` directory and use Pydantic to represent them.
In theory we should derive the models for both the UI side and the
server side using Swagger or something similar, but in practice that
seems like a lot of work for what are pretty trivial bits of code, and
keeping them in sync manually is not hard.

One thing that is not obvious about backend services is that you get a
brand new object on each HTTP request to the backend.
If you need to maintain state between requests, you cannot do it in-process.
For servers that need to cache state, I have been using the filesystem
to do this, in the user's `$HOME/.cache` directory.

#### Add the route

In the top-level `__init__.py` (that is, in the `rsp_jupyter_extensions`
directory), add your new handler (whose route should start with
`/rubin`) to the map in `_setup_handlers()`.
This will load your server extension into JupyterLab and make it
accessible via the route you choose.

### Developing the UI

Adding a new TypeScript component is done in the `src` top-level directory.

#### Choose a token

First, if your extension includes a UI widget (most do, but not all; for
instance, the environment extension extracts the environment from the
server side for the UI's consumption, but does not itself have any
user-visible interface in the browser), assign a token (an arbitrary
string) to the widget in `tokens.ts`.

#### Write the extension

The extension should get its own `.ts` file in the `src` directory; when
you export the extension, its `id` attribute should be the token and its
`autostart` attribute should be set to `false`.
That is because it will be activated by the top-level index.

Note that, once you have the environment, you can use the `logMessage()`
function to log messages to the console at a specified level.
Usually, `INFO` or higher messages will be shown, but if `Enable debug
logging` was checked on the spawn page, you will get `DEBUG` messages
too.
This is often extremely handy for determining why your extension isn't working.

Your extension will probably consume a JSON object via an `apiRequest()`
call to the back end and take action based on the contents of that
object's fields.

#### Update the index to load the extension

Finally, the top-level index, in `index.ts`, should be modified to load
your new extension at the appropriate place in the order.

That place is very likely after the environment has been loaded, and in
general should probably go towards the bottom of the order.
This explicit activation is why individual components should not be
autostarted.

Look at the existing `index.ts` for the way progress log messages are
formatted.
Maintaining this format makes it easier to use the browser console to
debug startup errors.

## Requirements

- JupyterLab >= 4.0.0

## Install

To install the extension, execute:

```bash
pip install rsp_jupyter_extensions
```

## Uninstall

To remove the extension, execute:

```bash
pip uninstall rsp_jupyter_extensions
```

## Troubleshoot

If you are seeing the frontend extension, but it is not working, check
that the server extension is enabled:

```bash
jupyter server extension list
```

If the server extension is installed and enabled, but you are not seeing
the frontend extension, check the frontend extension is installed:

```bash
jupyter labextension list
```

## Contributing

### Development install

Note: You will need NodeJS to build the extension package.

The `jlpm` command is JupyterLab's pinned version of
[yarn](https://yarnpkg.com/) that is installed with JupyterLab. You may use
`yarn` or `npm` in lieu of `jlpm` below.

```bash
# Clone the repo to your local environment
# Change directory to the rsp_jupyter_extensions directory
# Install package in development mode
pip install -e ".[test]"
# Link your development version of the extension with JupyterLab
jupyter labextension develop . --overwrite
# Server extension must be manually installed in develop mode
jupyter server extension enable rsp_jupyter_extensions
# Rebuild extension Typescript source after making changes
jlpm build
```

You can watch the source directory and run JupyterLab at the same time in different terminals to watch for changes in the extension's source and automatically rebuild the extension.

```bash
# Watch the source directory in one terminal, automatically rebuilding when needed
jlpm watch
# Run JupyterLab in another terminal
jupyter lab
```

With the watch command running, every saved change will immediately be built locally and available in your running JupyterLab. Refresh JupyterLab to load the change in your browser (you may need to wait several seconds for the extension to be rebuilt).

By default, the `jlpm build` command generates the source maps for this extension to make it easier to debug using the browser dev tools. To also generate source maps for the JupyterLab core extensions, you can run the following command:

```bash
jupyter lab build --minimize=False
```

### Development uninstall

```bash
# Server extension must be manually disabled in develop mode
jupyter server extension disable rsp_jupyter_extensions
pip uninstall rsp_jupyter_extensions
```

In development mode, you will also need to remove the symlink created by `jupyter labextension develop`
command. To find its location, you can run `jupyter labextension list` to figure out where the `labextensions`
folder is located. Then you can remove the symlink named `rsp-jupyter-extensions` within that folder.

### Testing the extension

#### Server tests

This extension is using [Pytest](https://docs.pytest.org/) for Python code testing.

Install test dependencies (needed only once):

```sh
pip install -e ".[test]"
# Each time you install the Python package, you need to restore the front-end extension link
jupyter labextension develop . --overwrite
```

To execute them, run:

```sh
pytest -vv -r ap --cov rsp_jupyter_extensions
```

#### Frontend tests

This extension is using [Jest](https://jestjs.io/) for JavaScript code testing.

To execute them, execute:

```sh
jlpm
jlpm test
```

#### Integration tests

This extension uses [Playwright](https://playwright.dev/docs/intro) for the integration tests (aka user level tests).
More precisely, the JupyterLab helper [Galata](https://github.com/jupyterlab/jupyterlab/tree/master/galata) is used to handle testing the extension in JupyterLab.

More information are provided within the [ui-tests](./ui-tests/README.md) README.

### Packaging the extension

See [RELEASE](RELEASE.md)
