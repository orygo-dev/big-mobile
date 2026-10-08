import { useState } from "react";

export default function LoginBackground({ preset = "aurora", imageUrl = "" }) {
  const [failedUrl, setFailedUrl] = useState("");
  const showImage = preset === "image" && imageUrl && imageUrl !== failedUrl;
  return (
    <div className={`login-background login-background-${showImage ? "image" : preset === "image" ? "aurora" : preset}`} aria-hidden="true">
      {showImage && <img src={imageUrl} alt="" className="login-background-photo" onError={() => setFailedUrl(imageUrl)} />}
      <div className="login-background-grid" />
      <div className="login-background-orbit login-background-orbit-blue" />
      <div className="login-background-orbit login-background-orbit-orange" />
      <div className="login-background-veil" />
    </div>
  );
}
