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
  const response = await ServerConnection.makeRequest(url, init, settings);
  const resp_j = await response.json();
  if (response.status !== 200) {
    throw new ServerConnection.ResponseError(response, resp_j.message);
  }
  return resp_j;
}
