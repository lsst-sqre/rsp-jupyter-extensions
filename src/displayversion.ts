// Copyright (c) LSST DM/SQuaRE
// Distributed under the terms of the MIT License.

import {
  JupyterFrontEnd, JupyterFrontEndPlugin
} from '@jupyterlab/application';


import {
  PageConfig
} from '@jupyterlab/coreutils';

interface EnvResponse {
  IMAGE_DESCRIPTION?: string;
  IMAGE_DIGEST?: string;
  JUPYTER_IMAGE_SPEC?: string;
  EXTERNAL_INSTANCE_URL?: string;
}

import {
  ServerConnection
} from '@jupyterlab/services';

import {
  IStatusBar
} from '@jupyterlab/statusbar';

import DisplayLabVersion from "./DisplayLabVersion"

import * as token from "./tokens"

/**
 * Activate the extension.
 */
export function activateRSPDisplayVersionExtension(app: JupyterFrontEnd, statusBar: IStatusBar): void {

  console.log('RSP DisplayVersion extension: loading...')

  let svcManager = app.serviceManager;

  let endpoint = PageConfig.getBaseUrl() + "rubin/environment"
  let init = {
    method: "GET"
  }
  let settings = svcManager.serverSettings

  apiRequest(endpoint, init, settings).then((res) => {
    let image_description = (res.IMAGE_DESCRIPTION || "")
    let image_digest = res.IMAGE_DIGEST
    let image_spec = res.JUPYTER_IMAGE_SPEC
    let instance_url = new URL(res.EXTERNAL_INSTANCE_URL || "")
    let hostname = " " + instance_url.hostname
    let digest_str = ""
    if (image_digest) {
      digest_str = " [" + image_digest.substring(0, 8) + "...]"
    }
    let imagename = ""
    if (image_spec) {
      let imagearr = image_spec.split("/");
      imagename = " (" + imagearr[imagearr.length - 1] + ")"
    }
    let label = image_description + digest_str + imagename + hostname


    const displayVersionWidget = new DisplayLabVersion(
      {
        source: label,
        title: image_description
      }
    );

    statusBar.registerStatusItem(
      token.DISPLAYVERSION_ID,
      {
        item: displayVersionWidget,
        align: "left",
        rank: 80,
        isActive: () => true
      }
    );
  }
  );

  function apiRequest(url: string, init: RequestInit, settings: ServerConnection.ISettings): Promise<EnvResponse> {
    /**
    * Make a request to our endpoint to get a pointer to a templated
    *  notebook for a given query
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
    return ServerConnection.makeRequest(url, init, settings).then(
      response => {
        if (response.status !== 200) {
          return response.json().then(data => {
            throw new ServerConnection.ResponseError(response, data.message);
          });
        }
        return response.json();
      }
    );
  }

  console.log('RSP DisplayVersion extension: ... loaded')
};

/**
 * Initialization data for the jupyterlab-lsstquery extension.
 */
const rspDisplayVersionExtension: JupyterFrontEndPlugin<void> = {
  activate: activateRSPDisplayVersionExtension,
  id: token.DISPLAYVERSION_ID,
  requires: [
    IStatusBar,
  ],
  autoStart: false,
};

export default rspDisplayVersionExtension;

