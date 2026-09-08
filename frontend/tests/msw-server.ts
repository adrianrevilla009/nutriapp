import { setupServer } from "msw/node";

// No default handlers -- every test registers exactly the handlers it
// needs via server.use(...), and onUnhandledRequest: "error" (tests/setup.ts)
// fails any test that makes a call it didn't explicitly mock (test-plan
// section 8: "no real call to any backend service anywhere in the
// unit/integration suite").
export const server = setupServer();
