import { ServerConnection } from '@jupyterlab/services';

// IJSONResponse is just "whatever we got, as JSON"
export interface IJSONResponse {
  value: {
    [key: string]: any;
  };
}

export async function apiRequest(
  url: string,
  init: RequestInit,
  settings: ServerConnection.ISettings
): Promise<IJSONResponse> {
  // Fake out URL check in makeRequest
  const resp = await ServerConnection.makeRequest(url, init, settings);
  const resp_j = await resp.json();
  if (resp.status !== 200) {
    throw new ServerConnection.ResponseError(resp, resp_j.message);
  }
  return resp_j;
}
