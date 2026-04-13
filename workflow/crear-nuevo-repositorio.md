## Objetivo

Cada repo nuevo en GoEcosystemDH debe tener la misma estructura base: branches, workflows, teams, protecciones y archivos estandar. Para eso existe un script automatizado.

## Prerequisitos

- gh CLI instalado y autenticado con permisos admin en la org
- Acceso al repo GoEcosystemDH/.github

## Uso

```bash
git clone https://github.com/GoEcosystemDH/.github.git
cd .github
./scripts/create-repo.sh nombre-del-repo "Descripcion del proyecto"
```

## Que hace automaticamente

| Paso | Accion |
|------|--------|
| 1 | Crear repo privado con descripcion |
| 2 | README, .gitignore, .env.example |
| 3 | Workflows: auto-pr, pr-metadata, labeler, pr-size |
| 4 | Branch develop (default) + main |
| 5 | Teams: DevOps-Infra (admin) + Development (push) |
| 6 | Auto-delete branches on merge |
| 7 | Rulesets org heredados |

## Checklist post-creacion

- [ ] Ejecutar create-repo.sh
- [ ] Agregar Dockerfile si aplica
- [ ] Agregar docker-compose.yml si aplica
- [ ] Agregar workflow CI/CD si aplica
- [ ] Configurar secrets si necesita
- [ ] PR de prueba para validar

