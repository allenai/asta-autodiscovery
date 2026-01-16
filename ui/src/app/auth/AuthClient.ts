// import {
//   Auth0Client as Auth0ClientClass,
//   createAuth0Client,
//   User,
// } from '@auth0/auth0-spa-js';

// const auth0Config = {
//   domain: process.env.NEXT_PUBLIC_AUTH0_DOMAIN || 'auth.example.com',
//   clientId:
//     process.env.NEXT_PUBLIC_AUTH0_CLIENT_ID ||
//     'YOUR_AUTH0_CLIENT_ID',
//   audience:
//     process.env.NEXT_PUBLIC_AUTH0_AUDIENCE ||
//     'https://autodiscovery.example.com',
//   requiredPermission:
//     process.env.NEXT_PUBLIC_AUTH0_REQUIRED_PERMISSION ||
//     'enroll:autodiscovery_v0',
// };

// class Auth0Client {
//   #auth0Client: Auth0ClientClass | undefined;

//   #getClient = async () => {
//     const AUTH0_DOMAIN = auth0Config.domain;
//     const AUTH0_CLIENT_ID = auth0Config.clientId;
//     const AUTH0_API_AUDIENCE = auth0Config.audience;

//     if (this.#auth0Client == null) {
//       if (!AUTH0_DOMAIN || !AUTH0_CLIENT_ID) {
//         throw new Error('Auth0 env variables are missing');
//       }

//       this.#auth0Client = await createAuth0Client({
//         domain: AUTH0_DOMAIN,
//         clientId: AUTH0_CLIENT_ID,
//         authorizationParams: {
//           // This isn't noted in the docs but it's needed if you want to use the token on the API end
//           audience: AUTH0_API_AUDIENCE,
//         },
//         // if we set up a custom auth0 domain we can get rid of useRefreshTokens and cacheLocation
//         useRefreshTokens: true,
//         cacheLocation: 'localstorage',
//       });
//     }

//     return this.#auth0Client;
//   };

//   getToken = async (useCache = true): Promise<string | undefined> => {
//     const client = await this.#getClient();

//     if (await client.isAuthenticated()) {
//       try {
//         if (!useCache) {
//           return await client.getTokenSilently({ cacheMode: 'off' });
//         } else {
//           return await client.getTokenSilently();
//         }
//       } catch (e) {
//         if (e instanceof Error) {
//           console.error(
//             `Something went wrong when getting the token (cache=${useCache}): ${e.message}\nLogging in again.`
//           );
//         }

//         // force logout in case there are expired tokens in localstorage, then relogin
//         await this.logout();
//         await this.login();
//         throw e;
//       }
//     }

//     return undefined;
//   };

//   isAuthenticated = async (): Promise<boolean> => {
//     const client = await this.#getClient();

//     return client.isAuthenticated();
//   };

//   getUserInfo = async (): Promise<User | undefined> => {
//     const client = await this.#getClient();
//     return await client.getUser();
//   };

//   login = async (): Promise<void> => {
//     const client = await this.#getClient();
//     const urlParams = new URLSearchParams(window.location.search);

//     client.loginWithRedirect({
//       authorizationParams: {
//         redirect_uri: `${window.location.origin}?${urlParams.toString()}`,
//         prompt: 'login', // Forces fresh login so user can choose which Google account to use and won't get stuck if they previously declined permissions during the flow
//       },
//       appState: {
//         returnTo:
//           window.location.pathname +
//           window.location.search +
//           window.location.hash,
//       },
//     });
//   };

//   handleLoginRedirect = async (): Promise<void> => {
//     const query = window.location.search;
//     if (query.includes('code=') && query.includes('state=')) {
//       const client = await this.#getClient();
//       const { appState } = await client.handleRedirectCallback();

//       // Redirect the user to the url they were on before the login
//       window.location.replace(appState?.returnTo || window.location.origin);
//     }
//   };

//   logout = async (): Promise<void> => {
//     const client = await this.#getClient();

//     await client.logout({
//       logoutParams: {
//         returnTo: window.location.origin,
//       },
//     });
//   };
// }

// export const auth0Client = new Auth0Client();
