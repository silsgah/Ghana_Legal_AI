export interface LegalExpert {
    id: string;
    name: string;
    field: string;
    era: string;
    icon: string;
    tagline: string;
    accentColor: string;
    description: string;
}

export const LEGAL_EXPERTS: LegalExpert[] = [
    {
        id: 'constitutional',
        name: 'Constitutional Expert',
        field: 'Ghana Constitution',
        era: '1992 - Present',
        icon: '⚖️',
        tagline: 'Specialist in the 1992 Constitution of Ghana and its amendments.',
        accentColor: '#fcd116', // Ghana Gold
        description: 'Expert on constitutional provisions, fundamental human rights, and the separation of powers in Ghana.',
    },
    {
        id: 'case_law',
        name: 'Case Law Analyst',
        field: 'Judicial Precedents',
        era: 'Modern Jurisprudence',
        icon: '📚',
        tagline: 'Specialist in Supreme Court and Court of Appeal rulings.',
        accentColor: '#006b3f', // Ghana Green
        description: 'Analytical expert focused on interpreting judgments, stare decisis, and the evolution of case law in Ghana.',
    },
    {
        id: 'legal_historian',
        name: 'Legal Historian',
        field: 'Legal History',
        era: 'Colonial to Republic',
        icon: '📜',
        tagline: 'Specialist in the evolution of the Ghanaian legal system.',
        accentColor: '#ce1126', // Ghana Red
        description: 'Expert on the historical development of Ghana law, from customary law to colonial ordinances and post-independence reforms.',
    },
];

export const getLegalExpert = (id: string): LegalExpert | undefined => {
    return LEGAL_EXPERTS.find((expert) => expert.id === id);
};
