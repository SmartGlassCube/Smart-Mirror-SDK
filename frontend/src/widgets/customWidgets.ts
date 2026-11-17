import * as React from 'react'
import * as JsxRuntime from 'react/jsx-runtime'
import type { CustomWidgetType } from '../types/mirror'
import type { WidgetComponent } from './defineWidget'
import { widgetRegistry } from './registry'

// Custom widgets arrive from the backend (WIDGET_TYPES, e.g. a Smart Mirror Studio project) as
// compiled CommonJS modules whose default export is the React component. They may import only React.
const MODULES: Record<string, unknown> = { react: React, 'react/jsx-runtime': JsxRuntime }

export function loadCompiledWidget(code: string): WidgetComponent {
  const module = { exports: {} as Record<string, unknown> }
  const require = (name: string) => {
    if (name in MODULES) return MODULES[name]
    throw new Error(`Custom widgets can only import 'react' (tried '${name}')`)
  }
  new Function('require', 'module', 'exports', 'React', code)(require, module, module.exports, React)
  const component = module.exports.default ?? module.exports
  if (typeof component !== 'function') throw new Error('The widget must `export default` a React component')
  return component as WidgetComponent
}

// Adds (or replaces) the custom widget types in the registry; built-in types keep their component.
export function registerCustomWidgets(types: CustomWidgetType[]) {
  for (const { type, name, code } of types) {
    if (builtinTypes.has(type)) {
      console.warn(`[widgets] Custom widget "${name}" uses the built-in type "${type}"; keeping the built-in one`)
      continue
    }
    try {
      widgetRegistry[type] = loadCompiledWidget(code)
    } catch (error) {
      console.error(`[widgets] Custom widget "${name}" (${type}) failed to load:`, error)
      const message = (error as Error).message
      widgetRegistry[type] = () => React.createElement('div', { className: 'widget' }, React.createElement('h2', null, name), React.createElement('div', null, `Failed to load: ${message}`))
    }
  }
}

const builtinTypes = new Set(Object.keys(widgetRegistry))
