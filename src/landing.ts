// Copyright (c) LSST DM/SQuaRE
// Distributed under the terms of the MIT License.

import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';

import { PageConfig } from '@jupyterlab/coreutils';

import { IDocumentManager } from '@jupyterlab/docmanager';

import { IMainMenu } from '@jupyterlab/mainmenu';

import * as token from './tokens';
import { IEnvResponse } from './environment';
import { LogLevels, logMessage } from './logger';
import { apiRequest } from './request';

interface ILandingEntryResult {
  dest: string;
  cached: boolean;
}

class LandingEntry implements ILandingEntryResult {
  dest: string;
  cached: boolean;

  constructor(inp: ILandingEntryResult) {
    (this.dest = inp.dest), (this.cached = inp.cached);
  }
}

export function activateRSPLandingExtension(
  app: JupyterFrontEnd,
  mainMenu: IMainMenu,
  docManager: IDocumentManager,
  env: IEnvResponse
): void {
  logMessage(LogLevels.INFO, env, 'rsp-landing: loading...');

  logMessage(LogLevels.DEBUG, env, '...requesting landing page...');
  ensureLandingPage(app, env).then(res => {
    if (res) {
      const dest = res.dest;
      docManager.open(dest);
      logMessage(LogLevels.DEBUG, env, `...opened landing page ${dest}...`);
    }
  });
  logMessage(LogLevels.INFO, env, 'rsp-landing: ...loaded.');
}

function ensureLandingPage(
  app: JupyterFrontEnd,
  env: IEnvResponse
): Promise<LandingEntry> {
  /**
   * Make a request to our endpoint to get the landing location
   *
   * @param settings - the settings for the current notebook server
   *
   * @param env - the server environment
   *
   * @returns a Promise resolved with the JSON response
   */

  const svcManager = app.serviceManager;
  const settings = svcManager.serverSettings;
  return apiRequest(
    PageConfig.getBaseUrl() + 'rubin/landing',
    { method: 'GET' },
    settings
  ).then(res => {
    logMessage(
      LogLevels.DEBUG,
      env,
      `rsp-landing: backend result ${JSON.stringify(res, undefined, 2)}`
    );
    const u_d = res as unknown;
    const i_le = u_d as ILandingEntryResult;
    const l_e = new LandingEntry(i_le);
    return l_e;
  });
}

/**
 * Initialization data for the jupyterlab-landing extension.
 */
const rspLandingExtension: JupyterFrontEndPlugin<void> = {
  activate: activateRSPLandingExtension,
  id: token.LANDING_ID,
  requires: [IMainMenu, IDocumentManager],
  autoStart: false
};

export default rspLandingExtension;
