import { JupyterFrontEnd } from '@jupyterlab/application';
import { PageConfig } from '@jupyterlab/coreutils';
import { apiRequest } from './request';

// INubladoConfigResponse encapsulates the Nublado configuration.
interface INubladoConfigResponse {
  container_size: string;
  debug: boolean;
  enable_rubin_query_menu: boolean;
  enable_tutorials_menu: boolean;
  file_browser_root: string;
  home_relative_to_file_browser_root: string;
  image: {
    description: string;
    digest: string;
    spec: string;
  };
  jupyterlab_config_dir: string;
  repertoire_base_url: string;
  resources: {
    limits: {
      cpu: number;
      memory: number;
    };
    requests: {
      cpu: number;
      memory: number;
    };
  };
  reset_user_env: boolean;
  runtime_mounts_dir: string;
}

export async function getServerConfig(
  app: JupyterFrontEnd
): Promise<INubladoConfigResponse> {
  const endpoint = PageConfig.getBaseUrl() + 'rubin/config';
  const init = {
    method: 'GET'
  };
  const svcManager = app.serviceManager;
  const settings = svcManager.serverSettings;

  const resp = await apiRequest(endpoint, init, settings);
  const u_resp = resp as unknown;
  return u_resp as INubladoConfigResponse;
}

export type { INubladoConfigResponse };
