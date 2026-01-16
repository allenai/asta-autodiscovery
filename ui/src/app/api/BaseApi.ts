// import { auth0Client } from '@/auth/AuthClient';

// export class BaseApi {
//   protected createDefaultHeaders = async () => {
//     const token = await auth0Client.getToken().catch((error: unknown) => {
//       console.error('Error getting token: ', error);
//       return undefined;
//     });

//     return {
//       'Content-Type': 'application/json',
//       ...(token ? { Authorization: `Bearer ${token}` } : {}),
//     };
//   };

//   async request<T>({
//     url,
//     method,
//     headers = {},
//     query = {},
//     body = '',
//     shouldThrowOnServerError = true,
//     ...options
//   }: {
//     url: string;
//     method: string;
//     headers?: Record<string, string>;
//     query?: Record<string, string>;
//     body?: any;
//     shouldThrowOnServerError?: boolean;
//     options?: RequestInit;
//   }): Promise<{
//     response: Response;
//     data: T;
//   }> {
//     let bodyStr: null | string = null;
//     switch (method.toUpperCase()) {
//       case 'GET':
//       case 'HEAD':
//         break;
//       default:
//         bodyStr = typeof body === 'string' ? body : JSON.stringify(body || {});
//         break;
//     }

//     const init: Record<string, any> = {
//       method,
//       headers: {
//         ...headers,
//       },
//       body: bodyStr,
//       ...options,
//     };

//     if (Object.keys(query).length > 0) {
//       url += '?' + new URLSearchParams(query).toString();
//     }

//     const resp = await fetch(url, init);
//     if (!resp.ok) {
//       const extraProps = {
//         url: url,
//         response: resp,
//       };
//       console.log(`Request failed with status ${resp.status}`, extraProps);
//       if (shouldThrowOnServerError) {
//         throw new Error(`Request failed with status ${resp.status}`);
//       }
//     }
//     const data = await resp.json();
//     return {
//       response: resp,
//       data,
//     };
//   }
// }
