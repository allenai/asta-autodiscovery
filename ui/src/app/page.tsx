import styles from './page.module.css'
import Header from './components/header'
import Footer from './components/footer';
import Main from './components/main';

interface SearchParams {
  question?: string;
  choices?: string[];
}

interface Props {
  searchParams: SearchParams;
}

interface Answer {
  answer: string;
  score: number;
}

export default async function Home({ searchParams }: Props) {
  let answer: Answer | undefined = undefined;
  if (searchParams.question && searchParams.choices) {
    const origin = process.env.API_ORIGIN ?? 'http://api:8000';
    const resp = await fetch(`${origin}/api/solve`, {
      method: 'POST',
      body: JSON.stringify(searchParams),
      headers: { 'Content-Type': 'application/json' }
    })
    if (!resp.ok) {
      throw new Error(`API request failed: ${resp.status}: ${resp.statusText}`)
    }
    answer = await resp.json()
  }

  const nf = Intl.NumberFormat('en-US', { style: 'percent', maximumFractionDigits: 2 })
  return (
    <>
      <Header />
      <Main>
        <h1 className={styles.title}>Skiff NextJS Template</h1>
        <p>This is an example Skiff application that uses <a href="https://nextjs.org">NextJS</a>.</p>
        <form method="get" action="/" className={styles.form}>
          <div className={styles.row}>
            <label htmlFor="question" className={styles.label}>Question:</label>
            <textarea
                id="question"
                name="question"
                placeholder="Enter a question…"
                rows={8}
                className={styles.text}
                defaultValue={searchParams.question} />
          </div>
          <div className={styles.row}>
            <label htmlFor="choice1" className={styles.label}>First Choice:</label>
            <input
              type="text"
              id="choice1"
              name="choices"
              placeholder="Enter first choice…"
              className={styles.text}
              defaultValue={searchParams.choices ? searchParams.choices[0] : ''} />
          </div>
          <div className={styles.row}>
            <label htmlFor="choice2" className={styles.label}>Second Choice:</label>
            <input
              type="text"
              id="choice2"
              name="choices"
              placeholder="Enter first choice…"
              className={styles.text}
              defaultValue={searchParams.choices ? searchParams.choices[1] : ''} />
          </div>
          <div><input type="submit" value="Submit" className={styles.button} /></div>
        </form>
        {answer && (
          <p>The answer is: <strong>{answer.answer}</strong> ({nf.format(answer.score)} confidence)</p>
        )}
      </Main>
      <Footer />
    </>
  );
}
