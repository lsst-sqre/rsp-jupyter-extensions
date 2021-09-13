// Copyright (c) LSST DM/SQuaRE
// Distributed under the terms of the MIT License.

import {
  JupyterFrontEnd, JupyterFrontEndPlugin
} from '@jupyterlab/application';


import {
  PageConfig
} from '@jupyterlab/coreutils';

interface VersionResponse {
  jupyter_image: string;
  image_description: string;
  image_digest: string;
  label: string;
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

  let endpoint = PageConfig.getBaseUrl() + "rubin/display_version"
  let init = {
    method: "GET"
  }
  let settings = svcManager.serverSettings

  apiRequest(endpoint, init, settings).then((res) => {
    const displayVersionWidget = new DisplayLabVersion(
      {
        source: res.label,
        title: res.image_description
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

  function apiRequest(url: string, init: RequestInit, settings: ServerConnection.ISettings): Promise<VersionResponse> {
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

  console.log('RSP DisplayVersion extension: ... ' + endpoint + ' loaded')
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

