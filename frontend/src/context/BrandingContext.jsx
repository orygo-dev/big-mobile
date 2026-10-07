import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const BrandingContext = createContext({ appName: "FieldCollector", logo: "", reload: () => {} });

export function BrandingProvider({ children }) {
  const [brand, setBrand] = useState({ appName: "FieldCollector", logo: "" });

  const reload = useCallback(() => {
    axios.get(`${BACKEND_URL}/api/branding`)
      .then(({ data }) => {
        const appName = data.app_name || "FieldCollector";
        setBrand({ appName, logo: data.logo || "" });
        if (appName) document.title = appName;
      })
      .catch(() => {});
  }, []);

  useEffect(() => { reload(); }, [reload]);

  return (
    <BrandingContext.Provider value={{ ...brand, reload }}>
      {children}
    </BrandingContext.Provider>
  );
}

export const useBranding = () => useContext(BrandingContext);
