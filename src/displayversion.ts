// Copyright (c) LSST DM/SQuaRE
// Distributed under the terms of the MIT License.

import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';

import { IStatusBar } from '@jupyterlab/statusbar';

import DisplayLabVersion from './DisplayLabVersion';

import { INubladoConfigResponse } from './config';

import { LogLevels, logMessage } from './logger';

import * as token from './tokens';

/**
 * Activate the extension.
 */
export function activateRSPDisplayVersionExtension(
  _: JupyterFrontEnd,
  statusBar: IStatusBar,
  cfg: INubladoConfigResponse
): void {
  logMessage(LogLevels.INFO, cfg, 'rsp-displayversion: loading...');

  const statusbar = cfg.statusbar || '';
  const image_description = cfg.image.description || '';

  const displayVersionWidget = new DisplayLabVersion({
    source: statusbar,
    title: image_description
  });

  statusBar.registerStatusItem(token.DISPLAYVERSION_ID, {
    item: displayVersionWidget,
    align: 'left',
    rank: 80,
    isActive: () => true
  });

  logMessage(LogLevels.INFO, cfg, 'rsp-displayversion: ... loaded');
}

/**
 * Initialization data for the RSPdisplayversionextension extension.
 */
const rspDisplayVersionExtension: JupyterFrontEndPlugin<void> = {
  activate: activateRSPDisplayVersionExtension,
  id: token.DISPLAYVERSION_ID,
  requires: [IStatusBar],
  autoStart: false
};

export default rspDisplayVersionExtension;
