// The only module the screens import from. Which backend answers is decided
// by EXPO_PUBLIC_API_URL, in one place, so no screen has to care.

import * as client from "./client";
import * as mock from "./mockBackend";
import { USE_MOCK_BACKEND } from "./config";

const backend = USE_MOCK_BACKEND ? mock : client;

export const searchPlaces = backend.searchPlaces;
export const planRoute = backend.planRoute;

export { ApiError } from "./client";
export * from "./types";
