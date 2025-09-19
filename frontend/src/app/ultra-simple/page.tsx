import './test.css';

export default function UltraSimple() {
  return (
    <div style={{padding: '2rem'}}>
      <div className="test-red">This should be red from test.css</div>
      <div className="bg-blue-500 text-white p-4">This should be blue from Tailwind</div>
      <div style={{backgroundColor: 'green', color: 'white', padding: '1rem'}}>This is inline green</div>
    </div>
  );
}