import React from 'react';
import Navbar from './Navbar';
import Footer from './Footer';
import Posts from './sections/Posts';
import Categories from './sections/Categories';
import About from './sections/About';
import Home from './sections/Home';

const Layout: React.FC = () => {
  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />
      
      <section id="home" className="min-h-screen pt-16">
        <Home />
      </section>

      <section id="posts" className="min-h-screen pt-16">
        <Posts />
      </section>

      <section id="categories" className="min-h-screen pt-16">
        <Categories />
      </section>

      <section id="about" className="min-h-screen pt-16">
        <About />
      </section>

      <Footer />
    </div>
  );
};

export default Layout; 