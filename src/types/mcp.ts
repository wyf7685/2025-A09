// StdioConnection 接口
interface StdioConnection {
  transport: 'stdio';
  /** The executable to run to start the server. */
  command: string;
  /** Command line arguments to pass to the executable. */
  args: string[];
  /** The environment to use when spawning the process. */
  env?: Record<string, string>;
  /** The working directory to use when spawning the process. */
  cwd?: string;
  /** The text encoding used when sending/receiving messages to the server. */
  encoding: string;
}

// SSEConnection 接口
interface SSEConnection {
  transport: 'sse';
  /** The URL of the SSE endpoint to connect to. */
  url: string;
  /** HTTP headers to send to the SSE endpoint */
  headers?: Record<string, any>;
  /** HTTP timeout */
  timeout: number;
  /** SSE read timeout */
  sse_read_timeout: number;
}

// StreamableHttpConnection 接口
interface StreamableHttpConnection {
  transport: 'streamable_http';
  /** The URL of the endpoint to connect to. */
  url: string;
  /** HTTP headers to send to the endpoint. */
  headers?: Record<string, any>;
  /** HTTP timeout. */
  timeout: number;
  /**
   * How long (in seconds) the client will wait for a new event before disconnecting.
   * All other HTTP operations are controlled by `timeout`.
   */
  sse_read_timeout: number;
  /** Whether to terminate the session on close */
  terminate_on_close: boolean;
}

// WebsocketConnection 接口
interface WebsocketConnection {
  transport: 'websocket';
  /** The URL of the Websocket endpoint to connect to. */
  url: string;
}

export type AnyMCPConnection =
  | StdioConnection
  | SSEConnection
  | StreamableHttpConnection
  | WebsocketConnection;

export interface MCPConnection {
  id: string;
  name: string;
  description?: string;
  connection: AnyMCPConnection;
}
