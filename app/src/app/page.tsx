import styles from './page.module.css'
import Header from './components/header'
import Footer from './components/footer';
import Main from './components/main';

export default function Home() {
  return (
    <>
      <Header />
      <Main>
        <h1 className={styles.title}>Skiff NextJS Template</h1>
        <p>This is an example Skiff application that uses <a href="https://nextjs.org">NextJS</a>.</p>
      </Main>
      <Footer />
    </>
  )
}
