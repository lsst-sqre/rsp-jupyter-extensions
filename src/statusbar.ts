// Copyright (c) LSST DM/SQuaRE
// Distributed under the terms of the MIT License.

import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';

import { IStatusBar } from '@jupyterlab/statusbar';

import DisplayStatusBar from './DisplayStatusBar';

import { INubladoConfigResponse } from './config';

import { LogLevels, logMessage } from './logger';

import * as token from './tokens';

/**
 * Activate the extension.
 */
export function activateRSPStatusBarExtension(
  _: JupyterFrontEnd,
  statusBar: IStatusBar,
  cfg: INubladoConfigResponse
): void {
  logMessage(LogLevels.INFO, cfg, 'rsp-statusbar: loading...');

  const statusbar = cfg.statusbar || '';
  const image_description = cfg.image.description || '';

  const displayStatusbarWidget = new DisplayStatusBar({
    source: statusbar,
    title: image_description
  });

  statusBar.registerStatusItem(token.DISPLAYVERSION_ID, {
    item: displayStatusbarWidget,
    align: 'left',
    rank: 80,
    isActive: () => true
  });

  logMessage(LogLevels.INFO, cfg, 'rsp-statusbar: ... loaded');
}

/**
 * Initialization data for the RSPStatusBar extension.
 */
const rspStatusBarExtension: JupyterFrontEndPlugin<void> = {
  activate: activateRSPStatusBarExtension,
  id: token.DISPLAYVERSION_ID,
  requires: [IStatusBar],
  autoStart: false
};

export default rspStatusBarExtension;
