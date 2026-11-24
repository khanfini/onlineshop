import { defineRailway, github, project, service, volume } from "railway/iac";
// This repository manages only its own resources in the environment. Other
// repositories export their own partial name.
// See https://docs.railway.com/infrastructure-as-code#multi-repo-projects
export const partial = "onlineshop";
export default defineRailway(() => {
  const onlineshop = service("onlineshop", {
    source: github("khanfini/onlineshop", { branch: "main", upstreamUrl: "https://github.com/khanfini/onlineshop" }),
    build: { buildEnvironment: "V3", builder: "NIXPACKS", buildCommand: "python manage.py collectstatic --noinput" },
    start: "python manage.py shell -c \"from django.conf import settings; from django.core.files.storage import default_storage; print('MEDIA_ROOT:', settings.MEDIA_ROOT); print('Media file:', default_storage.exists('products/argan_elixir_luxury.jpg')); print('Media directory:', default_storage.listdir('products'))\" && gunicorn trustsite.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120",
    healthcheck: "/health/",
    healthcheckTimeout: 300,
    preDeploy: "python manage.py migrate --noinput && mkdir -p /media/products && cp -av /app/media/products/. /media/products/ && ls -l /media/products/argan_elixir_luxury.jpg",
    volumeMounts: { "/media": volume("onlineshop-volume", { region: "iad", sizeMB: 500 }) },
    replicas: { "iad": 1 },
  });

  return project("alert-simplicity", {
    variables: { managed: false },
    resources: [onlineshop],
  });
});
