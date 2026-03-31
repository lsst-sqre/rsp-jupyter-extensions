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

import { PageConfig } from '@jupyterlab/coreutils';

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

  const image_description = cfg.image.description || '';
  const image_digest = cfg.image.digest;
  const image_spec = cfg.image.spec;

  let hostname = PageConfig.getOption('hubHost');
  // Not entirely accurate, but works for now.  Fix this with
  // service discovery.
  if (hostname.substring(0, 3) === 'nb.') {
    hostname = hostname.substring(3);
  }
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
    /* First try to get digest out of image spec (nublado v3) */
    const imagearr = image_spec.split('/');
    const pullname = imagearr[imagearr.length - 1];
    const partsarr = pullname.split('@');
    if (partsarr.length === 2) {
      /* Split name and sha; "sha256:" is seven characters */
      digest_str = ' [' + partsarr[1].substring(7, 7 + 8) + '...]';
      imagename = ' (' + partsarr[0] + ')';
    } else {
      /* Nothing to split; image name is the name we pulled by */
      imagename = ' (' + pullname + ')';
    }
    if (digest_str === '' && image_digest) {
      /* No digest in spec?  Well, did we set IMAGE_DIGEST?
         Yes, if we are nubladov2. */
      digest_str = ' [' + image_digest.substring(0, 8) + '...]';
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
