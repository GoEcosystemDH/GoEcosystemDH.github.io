# GoEcosystemDH — Canal Informativo

Sitio oficial de la organización **GoEcosystemDH** para comunicar anuncios, procesos y documentación de plataforma.

URL pública: **https://goecosystemdh.github.io/**

## Estructura

| Ruta | Propósito |
|------|-----------|
| `/` (`index.html`) | Landing principal con anuncios y accesos directos |
| `/branch-cleanup.html` | Proceso de limpieza de ramas |
| `/homologacion/` | Guías de homologación |
| `/workflow/` | Flujos y procesos de trabajo |
| `/WIKI-INDEX.md` | Índice general |

## Cómo publicar contenido

1. Crear rama desde `main` siguiendo la convención `docs/<tema>` o `fix/<tema>`.
2. Agregar/editar archivos HTML o Markdown en la ruta correspondiente.
3. Abrir PR a `main`.
4. Al hacer merge, GitHub Pages publica automáticamente.

## Notas técnicas

- El archivo `.nojekyll` está presente para evitar el procesamiento de Jekyll y servir los HTML tal cual.
- Este repo reemplaza el antiguo `docs/` del repo `.github`, que no podía ser servido por GitHub Pages por la limitación de nombres con punto.
