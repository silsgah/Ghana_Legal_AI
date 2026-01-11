/**
 * Philosopher Data with Metadata
 * Centralized configuration for all philosophers
 */

export interface Philosopher {
    id: string;
    name: string;
    avatar: string;
    era: string;
    field: string;
    tagline: string;
    accentColor: string;
}

export const PHILOSOPHERS: Philosopher[] = [
    {
        id: 'socrates',
        name: 'Socrates',
        avatar: '/philosophers/socrates.png',
        era: '470-399 BC',
        field: 'Ethics & Epistemology',
        tagline: 'I know that I know nothing',
        accentColor: '#8b5cf6',
    },
    {
        id: 'plato',
        name: 'Plato',
        avatar: '/philosophers/plato.png',
        era: '428-348 BC',
        field: 'Metaphysics & Politics',
        tagline: 'The cave allegory awaits',
        accentColor: '#6366f1',
    },
    {
        id: 'aristotle',
        name: 'Aristotle',
        avatar: '/philosophers/aristotle.png',
        era: '384-322 BC',
        field: 'Logic & Natural Philosophy',
        tagline: 'Excellence is a habit',
        accentColor: '#0ea5e9',
    },
    {
        id: 'descartes',
        name: 'René Descartes',
        avatar: '/philosophers/descartes.png',
        era: '1596-1650',
        field: 'Rationalism & Mind-Body',
        tagline: 'Cogito, ergo sum',
        accentColor: '#f59e0b',
    },
    {
        id: 'leibniz',
        name: 'Gottfried Wilhelm Leibniz',
        avatar: '/philosophers/leibniz.png',
        era: '1646-1716',
        field: 'Mathematics & Metaphysics',
        tagline: 'Best of all possible worlds',
        accentColor: '#10b981',
    },
    {
        id: 'ada_lovelace',
        name: 'Ada Lovelace',
        avatar: '/philosophers/ada.png',
        era: '1815-1852',
        field: 'Computing & Mathematics',
        tagline: 'First computer programmer',
        accentColor: '#ec4899',
    },
    {
        id: 'turing',
        name: 'Alan Turing',
        avatar: '/philosophers/turing.png',
        era: '1912-1954',
        field: 'Computer Science & AI',
        tagline: 'Can machines think?',
        accentColor: '#14b8a6',
    },
    {
        id: 'chomsky',
        name: 'Noam Chomsky',
        avatar: '/philosophers/chomsky.png',
        era: '1928-present',
        field: 'Linguistics & Cognition',
        tagline: 'Language is innate',
        accentColor: '#f97316',
    },
    {
        id: 'searle',
        name: 'John Searle',
        avatar: '/philosophers/searle.png',
        era: '1932-present',
        field: 'Philosophy of Mind',
        tagline: 'The Chinese Room',
        accentColor: '#a855f7',
    },
    {
        id: 'dennett',
        name: 'Daniel Dennett',
        avatar: '/philosophers/dennett.png',
        era: '1942-2024',
        field: 'Consciousness & Evolution',
        tagline: 'Consciousness explained',
        accentColor: '#22c55e',
    },
];

export function getPhilosopher(id: string): Philosopher | undefined {
    return PHILOSOPHERS.find((p) => p.id === id);
}

export function getPhilosopherName(id: string): string {
    return getPhilosopher(id)?.name ?? 'Philosopher';
}
