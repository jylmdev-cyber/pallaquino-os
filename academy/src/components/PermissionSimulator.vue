<script setup lang="ts">
import { computed, ref } from 'vue';
import { APPROVAL_TEXT, SCENARIOS, deriveApproval, deriveRisk } from '../lib/permissions';

const scenarioId = ref(SCENARIOS[0].id);
const hasGrant = ref(false);
const decision = ref<'' | 'approved' | 'rejected'>('');

const scenario = computed(() => SCENARIOS.find((s) => s.id === scenarioId.value)!);
const approval = computed(() => deriveApproval(scenario.value.operation, scenario.value.trust, scenario.value.capabilities));
const risk = computed(() => deriveRisk(scenario.value.operation, scenario.value.capabilities));
const outcome = computed(() => {
	if (approval.value === 'contract') return { status: 'COMPLETED', text: 'La pasarela permite la llamada: el grant de tarea del agente cubre FILE_READ.' };
	if (approval.value === 'grant') return hasGrant.value
		? { status: 'COMPLETED', text: 'Hay un grant activo que cubre esta herramienta y esta operación: la llamada se ejecuta y queda auditada.' }
		: { status: 'DENIED', text: 'No hay grant: la pasarela deniega la llamada (exit 5 en la CLI). Deny by default.' };
	if (decision.value === 'approved') return { status: 'COMPLETED', text: 'Aprobaste esta llamada exacta: se ejecuta una vez y la aprobación se consume.' };
	if (decision.value === 'rejected') return { status: 'DENIED', text: 'Rechazaste la llamada: no se ejecuta nada.' };
	return { status: 'APPROVAL_REQUIRED', text: 'La llamada espera tu decisión (exit 3 en la CLI). Un grant no basta.' };
});

function pick(id: string) {
	scenarioId.value = id; hasGrant.value = false; decision.value = '';
}
</script>

<template>
	<section class="perm" aria-labelledby="perm-title">
		<h2 id="perm-title">Simulador de permisos</h2>
		<p class="muted">Modelo educativo de la pasarela de herramientas de PALLAQUINO 0.5.0. <strong>No realiza ninguna acción real.</strong></p>
		<fieldset class="scenarios">
			<legend>Una herramienta solicita…</legend>
			<label v-for="s in SCENARIOS" :key="s.id"><input type="radio" name="perm-scenario" :checked="s.id === scenarioId" @change="pick(s.id)" /> {{ s.label }}</label>
		</fieldset>
		<dl class="facts">
			<dt>Herramienta</dt><dd><code>{{ scenario.toolId }}</code> ({{ scenario.source }}, confianza {{ scenario.trust }})</dd>
			<dt>Permiso requerido</dt><dd>{{ scenario.capabilities.join(', ') }} · operación {{ scenario.operation }}</dd>
			<dt>Riesgo derivado</dt><dd>{{ risk }}</dd>
			<dt>Alcance</dt><dd>este proyecto · el agente que llama · esta herramienta · esta operación</dd>
			<dt>Política</dt><dd>{{ approval }}: {{ APPROVAL_TEXT[approval] }}</dd>
		</dl>
		<p>{{ scenario.explanation }}</p>
		<div class="actions">
			<label v-if="approval === 'grant'"><input v-model="hasGrant" type="checkbox" /> Simular que existe <code>pallaquino permissions grant {{ scenario.toolId }}</code></label>
			<template v-if="approval === 'per_call'">
				<button type="button" @click="decision = 'approved'">Aprobar esta llamada</button>
				<button type="button" class="reject" @click="decision = 'rejected'">Rechazar</button>
			</template>
		</div>
		<p :class="['outcome', outcome.status.toLowerCase()]" aria-live="polite"><strong>{{ outcome.status }}</strong> · {{ outcome.text }}</p>
	</section>
</template>

<style scoped>
.perm { border: 1px solid var(--sl-color-gray-5); border-radius: 0.75rem; padding: 1rem 1.25rem; margin-block: 1.5rem; }
h2 { margin-top: 0; }
.muted { color: var(--sl-color-gray-2); font-size: var(--sl-text-sm); }
.scenarios { border: 0; padding: 0; margin: 0 0 0.75rem; }
.scenarios legend { font-weight: 600; margin-bottom: 0.25rem; }
.scenarios label { display: block; padding: 0.15rem 0; cursor: pointer; }
.facts dt { font-weight: 600; margin-top: 0.3rem; } .facts dd { margin: 0; }
.actions { display: flex; gap: 0.75rem; flex-wrap: wrap; align-items: center; }
.actions button { border: 1px solid var(--academy-success); background: transparent; color: var(--sl-color-white); border-radius: 0.5rem; padding: 0.35rem 0.8rem; cursor: pointer; }
.actions .reject { border-color: var(--academy-danger); }
.outcome { margin-top: 0.75rem; padding: 0.5rem 0.75rem; border-radius: 0.5rem; border-inline-start: 4px solid var(--sl-color-gray-4); background: var(--sl-color-gray-6); }
.outcome.completed { border-color: var(--academy-success); } .outcome.denied { border-color: var(--academy-danger); } .outcome.approval_required { border-color: var(--academy-warning); }
button:focus-visible, input:focus-visible { outline: 3px solid var(--sl-color-accent-high); outline-offset: 2px; }
</style>
