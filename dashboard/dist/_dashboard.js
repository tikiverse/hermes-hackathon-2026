
/* Hermes dashboard registration: wraps the framework-free UI in a React component. */
(function () {
  "use strict";
  var SDK = window.__HERMES_PLUGIN_SDK__;
  if (!SDK || !window.__HERMES_PLUGINS__) return;
  var React = SDK.React;
  function EvalpadPage() {
    var ref = React.useRef(null);
    React.useEffect(function () {
      if (ref.current) {
        window.EvalpadUI.mount(ref.current, { apiBase: "/api/plugins/evalpad", fetchJSON: SDK.fetchJSON });
      }
    }, []);
    return React.createElement("div", { ref: ref });
  }
  window.__HERMES_PLUGINS__.register("evalpad", EvalpadPage);
})();
