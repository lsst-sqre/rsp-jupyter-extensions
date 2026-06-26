// Copyright (c) LSST DM/SQuaRE
// Distributed under the terms of the MIT License.

import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';

import { IFileBrowserFactory } from '@jupyterlab/filebrowser';

import { ITranslator, nullTranslator } from '@jupyterlab/translation';

import { LabIcon } from '@jupyterlab/ui-components';

import { INubladoConfigResponse } from './config';

import { LogLevels, logMessage } from './logger';

import * as token from './tokens';

/**
 * The standard JupyterLab folder icon (from @jupyterlab/ui-components'
 * filetype/folder.svg) with a light-gray "C" superimposed, to mark the
 * collaborative file browser as distinct from the user's own.
 */
const COLLAB_FOLDER_SVG = `<svg xmlns="http://www.w3.org/2000/svg" width="16" viewBox="0 0 24 24">
  <path fill="#616161" d="M10 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8z" class="jp-icon3 jp-icon-selectable"/>
  <text x="12" y="17" font-size="11" text-anchor="middle" font-family="sans-serif" fill="#dbdbdb">C</text>
</svg>`;

const collabFolderIcon = new LabIcon({
  name: 'rsp-jupyterlab:collab-folder',
  svgstr: COLLAB_FOLDER_SVG
});

// Sleep helper function.
const sleep = (ms: number) => new Promise(r => setTimeout(r, ms));

/**
 * Activate the collab extension.
 *
 * Creates a second file browser in the left sidebar, rooted at the path
 * `collab` relative to the default drive root.  The caller is responsible for
 * gating activation on `cfg.collab_dir` being a non-empty string.
 */
export async function activateRSPCollabExtension(
  app: JupyterFrontEnd,
  factory: IFileBrowserFactory,
  cfg: INubladoConfigResponse,
  translator: ITranslator | null
): Promise<void> {
  logMessage(LogLevels.INFO, cfg, 'rsp-collab: loading...');

  // createFileBrowser uses the default drive (driveName ''), i.e. the same
  // contents root as the default file browser.  restore:false + auto:false so
  // the browser deterministically opens at `collab` on every reload rather
  // than restoring a previously-visited directory.
  const trans = (translator ?? nullTranslator).load('jupyterlab');
  const browser = factory.createFileBrowser(token.COLLAB_ID, {
    auto: false,
    restore: false
  });

  browser.title.icon = collabFolderIcon;
  browser.title.caption = trans.__('Collaborative Files');
  browser.node.setAttribute('role', 'region');
  browser.node.setAttribute(
    'aria-label',
    trans.__('Collab File Browser Section')
  );

  // rank 101 places this directly below the default file browser (rank 100).
  app.shell.add(browser, 'left', { rank: 101, type: 'Collab File Browser' });

  // `collab` may not exist yet (it will eventually be a symlink).  model.cd()
  // swallows a 404 internally -- it logs, emits connectionFailure, falls back
  // to the root, and still resolves -- so a missing directory is tolerated.
  // The try/catch is defensive in case that contract ever changes.

  // For right now, the sciplat-lab startup ensures that if the environment
  // variable NUBLADO_COLLAB_DIR is set, $HOME/collab is set up (assuming it
  // did not already exist) as a symbolic link to it.

  // If the user has their own $HOME/collab already, the browser will point
  // to it but the contents will be whatever the user put there, not the
  // link to NUBLADO_COLLAB_DIR.

  // There appears to be a race condition such that the symlink may not be
  // available immediately, so we retry up to three times.

  const home = cfg.home_relative_to_file_browser_root;
  const collabPath = home ? `${home}/collab` : 'collab';
  logMessage(
    LogLevels.INFO,
    cfg,
    `...attempting to open directory at ${collabPath}`
  );
  for (let i = 0; i < 3; i++) {
    try {
      await browser.model.cd(collabPath);
      break;
    } catch (error) {
      logMessage(
        LogLevels.WARNING,
        cfg,
        `rsp-collab: {i+1}/3: could not navigate to 'collab': ${error}`
      );
      await sleep(1000); // 1 second
    }
  }

  logMessage(LogLevels.INFO, cfg, 'rsp-collab: ... loaded');
}

/**
 * Initialization data for the RSPCollab extension.
 */
const rspCollabExtension: JupyterFrontEndPlugin<void> = {
  activate: activateRSPCollabExtension,
  id: token.COLLAB_ID,
  description: 'Secondary Filebrowser for collaborative files in the RSP',
  requires: [IFileBrowserFactory],
  optional: [ITranslator],
  autoStart: false
};

export default rspCollabExtension;
