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

export function activateRSPLandingExtension(
  app: JupyterFrontEnd,
  mainMenu: IMainMenu,
  docManager: IDocumentManager,
  env: IEnvResponse
): void {
  logMessage(LogLevels.INFO, env, 'rsp-landing: loading...');

  openLandingPage(app, docManager).then(() => {});
}

async function openLandingPage(
  app: JupyterFrontEnd,
  docManager: IDocumentManager
): Promise<void> {
  const svcManager = app.serviceManager;
  const settings = svcManager.serverSettings;
  try {
    await apiRequest(
      PageConfig.getBaseUrl() + 'rubin/landing',
      { method: 'GET' },
      settings
    );
  } catch (error) {
    console.error(`Error getting landing page ${error}`);
    throw new Error(`Failed to get landing page: ${error}`);
  }
  docManager.openOrReveal('.cache/landing_page.md');
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
