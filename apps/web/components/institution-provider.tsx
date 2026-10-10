"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  DEFAULT_INSTITUTION_CONFIG,
  applyBrandTheme,
  fetchInstitutionConfig,
  formatLocalizedDistance,
  formatLocalizedSpeed,
  type InstitutionConfig,
} from "@/lib/institution";

import { isDemoAuthEnabled } from "@/lib/auth-session";

interface InstitutionContextValue {
  config: InstitutionConfig;
  isLoaded: boolean;
  configurationError: boolean;
  retryConfiguration: () => void;
  setPrimaryColor: (hex: string) => void;
  formatDistance: (meters: number) => string;
  formatSpeed: (kmh: number) => string;
  formatCurrency: (amount: number, locale?: string) => string;
}

const InstitutionContext = createContext<InstitutionContextValue>({
  config: DEFAULT_INSTITUTION_CONFIG,
  isLoaded: false,
  configurationError: false,
  retryConfiguration: () => {},
  setPrimaryColor: () => {},
  formatDistance: (meters: number) => `${meters} m`,
  formatSpeed: (kmh: number) => `${kmh} km/h`,
  formatCurrency: (amount: number) => `${amount} EUR`,
});

export function InstitutionProvider({
  initialConfig,
  children,
}: {
  initialConfig?: InstitutionConfig;
  children: ReactNode;
}) {
  const [config, setConfig] = useState<InstitutionConfig>(
    initialConfig || DEFAULT_INSTITUTION_CONFIG,
  );
  const [isLoaded, setIsLoaded] = useState(Boolean(initialConfig));
  const [configurationError, setConfigurationError] = useState(false);
  const [reload, setReload] = useState(0);
  const retryConfiguration = useCallback(() => setReload((value) => value + 1), []);

  useEffect(() => {
    let isCancelled = false;
    const controller = new AbortController();

    fetchInstitutionConfig(controller.signal)
      .then((loaded) => {
        if (!isCancelled) {
          setConfigurationError(loaded.configuration_status === "unavailable" && !isDemoAuthEnabled());
          setConfig(loaded);
          setIsLoaded(true);
          if (loaded.configuration_status !== "unavailable") document.title = `${loaded.brand_name} — Road safety intelligence`;
          if (loaded.brand_primary_color) {
            applyBrandTheme(loaded.brand_primary_color);
          }
        }
      })
      .catch(() => {
        if (!isCancelled) {
          setIsLoaded(true);
        }
      });

    return () => {
      isCancelled = true;
      controller.abort();
    };
  }, [reload]);

  const setPrimaryColor = useCallback((hex: string) => {
    setConfig((prev) => ({
      ...prev,
      brand_primary_color: hex,
    }));
    applyBrandTheme(hex);
  }, []);

  const formatDistance = useCallback(
    (meters: number) => {
      return formatLocalizedDistance(meters, config.units.distance);
    },
    [config.units.distance],
  );

  const formatSpeed = useCallback(
    (kmh: number) => {
      return formatLocalizedSpeed(kmh, config.units.speed);
    },
    [config.units.speed],
  );

  const formatCurrency = useCallback(
    (amount: number, locale = "en-GB") => {
      try {
        return new Intl.NumberFormat(locale, {
          style: "currency",
          currency: config.units.currency || "EUR",
          maximumFractionDigits: 0,
        }).format(amount);
      } catch {
        return `${amount} ${config.units.currency}`;
      }
    },
    [config.units.currency],
  );

  const value = useMemo<InstitutionContextValue>(
    () => ({
      config,
      isLoaded,
      configurationError,
      retryConfiguration,
      setPrimaryColor,
      formatDistance,
      formatSpeed,
      formatCurrency,
    }),
    [config, isLoaded, configurationError, retryConfiguration, setPrimaryColor, formatDistance, formatSpeed, formatCurrency],
  );

  return (
    <InstitutionContext.Provider value={value}>
      {children}
    </InstitutionContext.Provider>
  );
}

export function useInstitution(): InstitutionContextValue {
  return useContext(InstitutionContext);
}
