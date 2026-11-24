import { defineRailway, github, project, service, volume } from "railway/iac";
// This repository manages only its own resources in the environment. Other
// repositories export their own partial name.
// See https://docs.railway.com/infrastructure-as-code#multi-repo-projects
export const partial = "onlineshop";
export default defineRailway(() => {
  const onlineshop = service("onlineshop", {
    source: github("khanfini/onlineshop", { branch: "main", upstreamUrl: "https://github.com/khanfini/onlineshop" }),
    build: { buildEnvironment: "V3", builder: "NIXPACKS", buildCommand: "python manage.py collectstatic --noinput" },
    start: "gunicorn trustsite.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120",
    healthcheck: "/health/",
    healthcheckTimeout: 300,
    preDeploy: "python manage.py migrate --noinput",
    volumeMounts: { "/media": volume("onlineshop-volume", { region: "iad", sizeMB: 500 }) },
    replicas: { "iad": 1 },
  });

  return project("alert-simplicity", {
    variables: { managed: false },
    resources: [onlineshop],
  });
});
