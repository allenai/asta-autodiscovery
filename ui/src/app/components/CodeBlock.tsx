import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import { Box, Button, alpha, styled, useTheme } from '@mui/material';
import * as React from 'react';
import SyntaxHighlighter from 'react-syntax-highlighter';
import { monokai } from 'react-syntax-highlighter/dist/esm/styles/hljs';

interface CodeBlockProps {
    code: string;
}

export const CodeBlock = ({ code }: CodeBlockProps) => {
    const theme = useTheme();
    const [isCopied, setIsCopied] = React.useState(false);
    const [isExpanded, setIsExpanded] = React.useState(false);
    const codeString = code.replace(/\n$/, '');
    const lines = codeString.split('\n');
    const totalLines = lines.length;
    const showToggleButton = totalLines > 10;

    const handleCopy = () => {
        navigator.clipboard.writeText(codeString).then(() => {
            setIsCopied(true);
            setTimeout(() => setIsCopied(false), 2000);
        });
    };

    const toggleIsExpanded = () => {
        setIsExpanded(!isExpanded);
    };

    const displayedCode =
        showToggleButton && !isExpanded ? lines.slice(0, 10).join('\n') : codeString;

    return (
        <CodeWrapper>
            <CopyButton onClick={handleCopy}>
                {isCopied ? 'Copied!' : <ContentCopyIcon sx={{ fontSize: '1rem' }} />}
            </CopyButton>
            <SyntaxHighlighter
                customStyle={{
                    backgroundColor: alpha(theme.color.black.hex, 0.6),
                    color: theme.color['cream-4'].hex,
                    margin: 0,
                    minHeight: '52px',
                }}
                showLineNumbers={true}
                style={monokai}
                wrapLines={true}>
                {displayedCode}
            </SyntaxHighlighter>
            {showToggleButton && (
                <ViewAllButton onClick={toggleIsExpanded}>
                    <span>{isExpanded ? 'View less' : `View all ${totalLines} lines`}</span>
                    <StyledIconBox>
                        <StyledIcon as={isExpanded ? KeyboardArrowUpIcon : KeyboardArrowDownIcon} />
                    </StyledIconBox>
                </ViewAllButton>
            )}
        </CodeWrapper>
    );
};

const CodeWrapper = styled('div')`
    margin-bottom: ${({ theme }) => theme.spacing(2)};
    position: relative;
`;

const CopyButton = styled(Button)`
    background-color: ${({ theme }) => theme.color['gray-80'].hex};
    border: none;
    border-radius: ${({ theme }) => theme.shape.borderRadius}px;
    color: ${({ theme }) => theme.color['cream-4'].hex};
    cursor: pointer;
    opacity: 0.6;
    padding: 6px 9px;
    position: absolute;
    right: 10px;
    top: 10px;
    transition: opacity 0.2s ease-in-out;

    &:hover {
        opacity: 1;
    }
`;

const StyledIconBox = styled(Box)`
    align-items: center;
    background-color: ${({ theme }) => theme.color['dark-teal-100'].hex};
    border-radius: ${({ theme }) => theme.shape.borderRadius}px;
    display: flex;
    justify-content: center;
    padding: ${({ theme }) => theme.spacing(1 / 8)};
    transition: background-color 0.2s ease-in-out;

    &:hover {
        background-color: ${({ theme }) => theme.color['teal-50'].hex};
    }
`;

const StyledIcon = styled(KeyboardArrowUpIcon)`
    &.MuiSvgIcon-root {
        color: ${({ theme }) => theme.color['green-100'].hex};
        font-size: 1rem;
    }
`;

const ViewAllButton = styled(Button)`
    align-items: center;
    background-color: ${({ theme }) => alpha(theme.color.black.hex, 0.4)};
    border: none;
    border-top: 1px solid #333;
    color: ${({ theme }) => theme.color['gray-30'].hex};
    display: flex;
    font-size: small;
    gap: ${({ theme }) => theme.spacing(1.2)};
    justify-content: flex-start;
    padding: ${({ theme }) => theme.spacing(1, 2)};
    width: 100%;
`;
