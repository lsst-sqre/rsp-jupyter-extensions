// Copyright (c) LSST DM/SQuaRE
// Distributed under the terms of the MIT License.

import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';

import { IStatusBar } from '@jupyterlab/statusbar';

import DisplayLabVersion from './DisplayLabVersion';

import { IEnvResponse } from './environment';

import { LogLevels, logMessage } from './logger';

import * as token from './tokens';

/**
 * Activate the extension.
 */
export function activateRSPDisplayVersionExtension(
  app: JupyterFrontEnd,
  statusBar: IStatusBar,
  env: IEnvResponse
): void {
  logMessage(LogLevels.INFO, env, 'rsp-displayversion: loading...');

  const image_description = env.IMAGE_DESCRIPTION || '';
  const image_digest = env.IMAGE_DIGEST;
  const image_spec = env.JUPYTER_IMAGE_SPEC;
  const instance_url = new URL(env.EXTERNAL_INSTANCE_URL || '');
  const hostname = ' ' + instance_url.hostname;
  const container_size = env.CONTAINER_SIZE || '';
  let size = '';
  if (container_size === '') {
    size = ' (' + env.CPU_LIMIT + ' CPU, ' + env.MEM_LIMIT + ' B)';
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

  logMessage(LogLevels.INFO, env, 'rsp-displayversion: ... loaded');
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
