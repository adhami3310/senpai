import { Html5QrcodeScanner } from "html5-qrcode";
import { useEffect } from "react";

const qrcodeRegionId = "html5qr-code-full-region";

export function Html5QrcodePlugin(props) {
  const {
    fps = undefined,
    qrbox = undefined,
    aspectRatio = undefined,
    disableFlip = undefined,
    verbose = undefined,
    qrCodeSuccessCallback = undefined,
    qrCodeErrorCallback = undefined,
    ...rest
  } = props;
  useEffect(() => {
    const config = {
      fps,
      qrbox,
      aspectRatio,
      disableFlip,
    };
    // Suceess callback is required.
    if (!qrCodeSuccessCallback) {
      throw "qrCodeSuccessCallback is required callback.";
    }
    const html5QrcodeScanner = new Html5QrcodeScanner(
      qrcodeRegionId,
      config,
      verbose === true
    );
    html5QrcodeScanner.render(qrCodeSuccessCallback, qrCodeErrorCallback);

    // cleanup function when component will unmount
    return () => {
      html5QrcodeScanner.clear().catch((error) => {
        console.error("Failed to clear html5QrcodeScanner. ", error);
      });
    };
  }, []);

  return <div id={qrcodeRegionId} {...rest} />;
}
