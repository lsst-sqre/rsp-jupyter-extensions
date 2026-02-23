// Copyright (c) LSST DM/SQuaRE
// Distributed under the terms of the MIT License.

import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';

import { IStatusBar } from '@jupyterlab/statusbar';

import DisplayLabVersion from './DisplayLabVersion';

import { LogLevels, logMessage } from './logger';

import * as token from './tokens';
import { INubladoConfigResponse } from './config';
import { IRepertoireResponse } from './discovery';

/**
 * Activate the extension.
 */
export function activateRSPDisplayVersionExtension(
  app: JupyterFrontEnd,
  statusBar: IStatusBar,
  cfg: INubladoConfigResponse,
  dsc: IRepertoireResponse
): void {
  logMessage(LogLevels.INFO, cfg, 'rsp-displayversion: loading...');

  const image_description = cfg.image.description || '';
  const image_digest = cfg.image.digest;
  const image_spec = cfg.image.spec;
  const hostname = dsc.environment_name; // Not supposed to use it this way.
  const container_size = cfg.container_size || '';
  let size = '';
  if (container_size === '') {
    size =
      ' (' +
      cfg.resources.limits.cpu +
      ' CPU, ' +
      cfg.resources.limits.memory +
      ' B)';
  } else {
    size = ' ' + container_size;
  }
  let digest_str = '';
  let imagename = '';
  if (image_spec) {
    const imagearr = image_spec.split('/');
    const pullname_digest = imagearr[imagearr.length - 1];
    const partsarr = pullname_digest.split('@');
    if (partsarr.length > 0) {
      imagename = ' (' + partsarr[0] + ')';
    }
    if (image_digest) {
      // "sha256:" is seven characters
      digest_str = ' [' + image_digest.substring(7, 7 + 8) + '...]';
    }
    const label = image_description + digest_str + imagename + size + hostname;

    const displayVersionWidget = new DisplayLabVersion({
      source: label,
      title: image_description
    });

    statusBar.registerStatusItem(token.DISPLAYVERSION_ID, {
      item: displayVersionWidget,
      align: 'left',
      rank: 80,
      isActive: () => true
    });
  }

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
