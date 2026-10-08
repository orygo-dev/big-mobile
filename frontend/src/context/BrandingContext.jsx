import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import api, { API } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

const BrandingContext = createContext({ appName: "FieldCollector", logo: "", loginBackground: { preset: "aurora", image_url: "" }, reload: () => {} });

export function BrandingProvider({ children }) {
  const { user } = useAuth();
  const [brand, setBrand] = useState({ appName: "FieldCollector", logo: "", loginBackground: { preset: "aurora", image_url: "" } });

  const reload = useCallback(() => {
    api.get(user ? "/company" : "/branding")
      .then(({ data }) => {
        const appName = data.app_name || "FieldCollector";
        const background = data.login_background || {};
        const imageUrl = background.image_url ? `${API.replace(/\/api$/, "")}${background.image_url}` : "";
        setBrand({ appName, logo: data.logo || "", loginBackground: { preset: background.preset || "aurora", image_url: imageUrl } });
        if (appName) document.title = appName;
      })
      .catch(() => {});
  }, [user]);

  useEffect(() => { reload(); }, [reload]);

  return (
    <BrandingContext.Provider value={{ ...brand, reload }}>
      {children}
    </BrandingContext.Provider>
  );
}

export const useBranding = () => useContext(BrandingContext);
