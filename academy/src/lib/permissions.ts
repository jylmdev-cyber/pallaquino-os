/**
 * Teaching model of PALLAQUINO's tool governance (pallaquino_cli/tools/contracts.py and permissions.py, 0.5.0).
 * Tests compare it with the real builtin tool contracts generated in src/data/generated/tools.json, so it cannot drift silently.
 */
export type Operation = 'READ_ONLY' | 'WRITE_OPERATION' | 'SENSITIVE_OPERATION' | 'DESTRUCTIVE_OPERATION' | 'EXTERNAL_SIDE_EFFECT';
export type Trust = 'builtin' | 'trusted' | 'untrusted';
export type Approval = 'contract' | 'grant' | 'per_call';
export type Risk = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

const RISK_ORDER: Risk[] = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'];
const OPERATION_RISK: Record<Operation, Risk> = { READ_ONLY: 'LOW', WRITE_OPERATION: 'MEDIUM', SENSITIVE_OPERATION: 'HIGH', EXTERNAL_SIDE_EFFECT: 'HIGH', DESTRUCTIVE_OPERATION: 'CRITICAL' };
const CAPABILITY_RISK: Record<string, Risk> = { SECRETS_ACCESS: 'CRITICAL', DEPLOYMENT: 'CRITICAL', CLOUD_MANAGEMENT: 'CRITICAL', DATABASE_WRITE: 'HIGH', NETWORK_WRITE: 'HIGH',
	GIT_WRITE: 'MEDIUM', FILE_WRITE: 'MEDIUM', CODE_EXECUTION: 'MEDIUM' };
const PER_CALL_CAPABILITIES = new Set(['SECRETS_ACCESS', 'DEPLOYMENT', 'CLOUD_MANAGEMENT', 'DATABASE_WRITE', 'NETWORK_WRITE']);

export function deriveRisk(operation: Operation, capabilities: string[]): Risk {
	const levels = [OPERATION_RISK[operation], ...capabilities.map((c) => CAPABILITY_RISK[c]).filter((r): r is Risk => Boolean(r))];
	return levels.reduce((a, b) => (RISK_ORDER.indexOf(b) > RISK_ORDER.indexOf(a) ? b : a));
}

export function deriveApproval(operation: Operation, trust: Trust, capabilities: string[]): Approval {
	if (operation === 'SENSITIVE_OPERATION' || operation === 'DESTRUCTIVE_OPERATION' || operation === 'EXTERNAL_SIDE_EFFECT') return 'per_call';
	if (capabilities.some((c) => PER_CALL_CAPABILITIES.has(c))) return 'per_call';
	if (operation === 'READ_ONLY' && trust === 'builtin') return 'contract';
	return 'grant';
}

export interface Scenario {
	id: string;
	label: string;
	toolId: string;
	source: string;
	trust: Trust;
	operation: Operation;
	capabilities: string[];
	explanation: string;
}

/** Example requests for the permission simulator; the first three use real builtin tools. */
export const SCENARIOS: Scenario[] = [
	{ id: 'leer', label: 'Leer README.md del workspace', toolId: 'core.files.read', source: 'builtin', trust: 'builtin', operation: 'READ_ONLY', capabilities: ['FILE_READ'],
		explanation: 'Lectura builtin dentro del workspace: basta con que el grant de tarea del agente incluya read_repository.' },
	{ id: 'escribir', label: 'Escribir docs/notas.md', toolId: 'core.files.write', source: 'builtin', trust: 'builtin', operation: 'WRITE_OPERATION', capabilities: ['FILE_WRITE'],
		explanation: 'Toda escritura necesita un grant explícito, con alcance y caducidad (pallaquino permissions grant).' },
	{ id: 'git-stage', label: 'Preparar cambios con git add', toolId: 'core.git.stage', source: 'builtin', trust: 'builtin', operation: 'WRITE_OPERATION', capabilities: ['GIT_WRITE'],
		explanation: 'Cambia el estado local de Git: necesita grant. PALLAQUINO no ofrece push como herramienta.' },
	{ id: 'mcp-sin-clasificar', label: 'Herramienta MCP sin clasificar (echo)', toolId: 'mcp.quality.echo', source: 'mcp', trust: 'untrusted', operation: 'EXTERNAL_SIDE_EFFECT', capabilities: ['CODE_EXECUTION'],
		explanation: 'PALLAQUINO no confía en las anotaciones del servidor: una herramienta MCP sin clasificar se trata como efecto externo y cada llamada requiere tu aprobación.' },
	{ id: 'deploy', label: 'Desplegar a producción', toolId: 'mcp.ops.deploy', source: 'mcp', trust: 'untrusted', operation: 'EXTERNAL_SIDE_EFFECT', capabilities: ['DEPLOYMENT'],
		explanation: 'Acción crítica: ningún grant la cubre; solo una aprobación humana para esos argumentos exactos, de un solo uso.' },
];

export const APPROVAL_TEXT: Record<Approval, string> = {
	contract: 'Permitido por el contrato del agente (lectura builtin).',
	grant: 'Requiere un grant: alcance (proyecto, agente, herramienta, operación), caducidad y usos máximos.',
	per_call: 'Requiere aprobación humana por llamada, ligada al digest de los argumentos y de un solo uso.',
};
