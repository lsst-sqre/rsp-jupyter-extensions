// Copyright (c) LSST DM/SQuaRE
// Distributed under the terms of the MIT License.

import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';

import { PageConfig } from '@jupyterlab/coreutils';

interface IEnvResponse {
  IMAGE_DESCRIPTION?: string;
  IMAGE_DIGEST?: string;
  JUPYTER_IMAGE_SPEC?: string;
  EXTERNAL_INSTANCE_URL?: string;
  CPU_LIMIT?: string;
  MEM_LIMIT?: string;
  CONTAINER_SIZE?: string;
}

import { ServerConnection } from '@jupyterlab/services';

import { IStatusBar } from '@jupyterlab/statusbar';

import DisplayLabVersion from './DisplayLabVersion';

import * as token from './tokens';

/**
 * Activate the extension.
 */
export function activateRSPDisplayVersionExtension(
  app: JupyterFrontEnd,
  statusBar: IStatusBar
): void {
  console.log('RSP DisplayVersion extension: loading...');

  const svcManager = app.serviceManager;

  const endpoint = PageConfig.getBaseUrl() + 'rubin/environment';
  const init = {
    method: 'GET'
  };
  const settings = svcManager.serverSettings;

  apiRequest(endpoint, init, settings).then(res => {
    const image_description = res.IMAGE_DESCRIPTION || '';
    const image_digest = res.IMAGE_DIGEST;
    const image_spec = res.JUPYTER_IMAGE_SPEC;
    const instance_url = new URL(res.EXTERNAL_INSTANCE_URL || '');
    const hostname = ' ' + instance_url.hostname;
    const container_size = res.CONTAINER_SIZE || '';
    let size = '';
    if (container_size === '') {
      size = ' (' + res.CPU_LIMIT + ' CPU, ' + res.MEM_LIMIT + ' B)';
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
  });

  function apiRequest(
    url: string,
    init: RequestInit,
    settings: ServerConnection.ISettings
  ): Promise<IEnvResponse> {
    /**
     * Make a request to our endpoint to get the version
     *
     * @param url - the path for the displayversion extension
     *
     * @param init - The GET for the extension
     *
     * @param settings - the settings for the current notebook server
     *
     * @returns a Promise resolved with the JSON response
     */
    // Fake out URL check in makeRequest
    return ServerConnection.makeRequest(url, init, settings).then(response => {
      if (response.status !== 200) {
        return response.json().then(data => {
          throw new ServerConnection.ResponseError(response, data.message);
        });
      }
      return response.json();
    });
  }

  console.log('RSP DisplayVersion extension: ... loaded');
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
