# Auto PR: develop → main

## Descripcion

Workflow automatizado que crea un Pull Request de `develop` hacia `main` cada vez que `develop` recibe cambios. Esto asegura que `main` se mantenga actualizada sin intervencion manual.

## Como funciona

```
Developer → PR feature/* → develop (merge con approval)
                                ↓
                    Push a develop dispara:
                    ├── Deploy a sandbox (si aplica)
                    └── Auto-PR workflow
                                ↓
                    ¿Existe PR abierto develop → main?
                        ├── NO → Crea PR nuevo
                        └── SI → Actualiza descripcion
                                ↓
                    DevOps/Lead aprueba → merge a main
                                ↓
                    Deploy a produccion
```

## Arquitectura

El workflow usa un patron de **reusable workflow**:

| Componente | Ubicacion | Proposito |
|------------|-----------|-----------|
| **Workflow reusable** | `GoEcosystemDH/.github/.github/workflows/auto-pr-to-main.yml` | Logica completa (crear/actualizar PR) |
| **Caller workflow** | `{cada-repo}/.github/workflows/auto-pr-to-main.yml` | Archivo pequeno que invoca al reusable |

Si se necesita cambiar la logica, **solo se edita el workflow reusable** en el repo `.github`.

## Caller workflow (en cada repo)

```yaml
name: "Auto PR: develop → main"
on:
  push:
    branches: [develop]
jobs:
  auto-pr:
    uses: GoEcosystemDH/.github/.github/workflows/auto-pr-to-main.yml@main
    secrets: inherit
```

## Permisos y bypass

| Rol | Puede aprobar/mergear |
|-----|----------------------|
| DevOps-Infra | Si (bypass) |
| Org Admins | Si (bypass) |
| Development | No (necesitan approval) |

## Agregar a un repo nuevo

```bash
mkdir -p .github/workflows
curl -sL https://raw.githubusercontent.com/GoEcosystemDH/.github/main/workflow-templates/auto-pr-caller.yml > .github/workflows/auto-pr-to-main.yml
git add . && git commit -m "ci: add auto-PR workflow" && git push origin develop
```
