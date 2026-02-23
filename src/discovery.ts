// Copyright (c) LSST DM/SQuaRE
// Distributed under the terms of the MIT License.

import { INubladoConfigResponse } from './config';
import { logMessage, LogLevels } from './logger';

interface IRepertoireService {
  [key: string]: {
    url: string;
    openapi?: string;
    versions?: {
      [key: string]: {
        url: string;
      };
    };
  };
}

// This is a very basic implementation of the Discovery response.
// cf. https://github.com/lsst-sqre/squareone/tree/main/packages/repertoire-client
// and especially
// https://github.com/lsst-sqre/squareone/blob/main/packages/repertoire-client/openapi.json
interface IRepertoireResponse {
  applications: string[];
  environment_name: string;
  datasets: {
    [key: string]: any; // Sloppy, but we don't need them for these extensions.
  };
  services: {
    ui: IRepertoireService;
    internal: IRepertoireService;
  };
}

export async function queryRepertoire(
  cfg: INubladoConfigResponse
): Promise<IRepertoireResponse> {
  const endpoint = cfg.repertoire_base_url;
  const empty_dsc = {
    applications: [],
    environment_name: '',
    datasets: {},
    services: {
      ui: {},
      internal: {}
    }
  };
  if (!endpoint) {
    logMessage(
      LogLevels.WARNING,
      cfg,
      'No service discovery endpoint; using empty document'
    );
    return empty_dsc as IRepertoireResponse;
  }
  try {
    const resp = await fetch(endpoint + '/discovery', {
      method: 'GET'
    });
    const result = await resp.json();
    const u_result = result as unknown;
    return u_result as IRepertoireResponse;
  } catch (error) {
    logMessage(
      LogLevels.WARNING,
      cfg,
      `Service discovery failed with "${error}"; using empty document`
    );
    return empty_dsc as IRepertoireResponse;
  }
}

export type { IRepertoireResponse };
